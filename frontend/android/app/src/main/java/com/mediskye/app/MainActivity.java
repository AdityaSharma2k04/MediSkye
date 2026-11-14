package com.mediskye.app;

import android.annotation.SuppressLint;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Bundle;
import android.util.Log;
import android.view.View;
import android.webkit.CookieManager;
import android.webkit.JavascriptInterface;
import android.webkit.WebSettings;
import android.webkit.WebView;

import com.getcapacitor.BridgeActivity;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;

public class MainActivity extends BridgeActivity {

    private static final String TAG = "MediSkyeNativeAuth";
    private static volatile int activeLoopbackPort = 0;
    private static volatile ServerSocket serverSocket = null;
    private volatile String pendingAuthIdToken = null;
    private volatile String pendingAuthAccessToken = null;

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        if (this.bridge != null && this.bridge.getWebView() != null) {
            WebView webView = this.bridge.getWebView();

            CookieManager cookieManager = CookieManager.getInstance();
            cookieManager.setAcceptCookie(true);
            cookieManager.setAcceptThirdPartyCookies(webView, true);

            WebSettings settings = webView.getSettings();
            settings.setJavaScriptCanOpenWindowsAutomatically(true);
            settings.setSupportMultipleWindows(true);

            String ua = settings.getUserAgentString();
            if (ua != null && ua.contains("; wv")) {
                ua = ua.replace("; wv", "");
            } else if (ua == null || ua.isEmpty()) {
                ua = "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36";
            }
            settings.setUserAgentString(ua);

            // Hardware-acceleration & overscroll optimization for 120 FPS
            webView.setLayerType(View.LAYER_TYPE_HARDWARE, null);
            webView.setOverScrollMode(View.OVER_SCROLL_NEVER);

            // Add JavaScript interface for 1-tap native Google Login loopback
            webView.addJavascriptInterface(new MediskyeNativeBridge(), "MediskyeNativeAuth");
        }

        handleAuthIntent(getIntent());
    }

    @Override
    public void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        handleAuthIntent(intent);
    }

    private void handleAuthIntent(Intent intent) {
        if (intent == null || intent.getData() == null) {
            return;
        }
        Uri data = intent.getData();
        if ("mediskye".equalsIgnoreCase(data.getScheme()) && "auth-callback".equalsIgnoreCase(data.getHost())) {
            String idToken = data.getQueryParameter("id_token");
            String accessToken = data.getQueryParameter("access_token");
            dispatchAuthTokensToWebView(idToken, accessToken);
        }
    }

    private void dispatchAuthTokensToWebView(final String idToken, final String accessToken) {
        pendingAuthIdToken = idToken;
        pendingAuthAccessToken = accessToken;
        runOnUiThread(new Runnable() {
            @Override
            public void run() {
                if (bridge != null && bridge.getWebView() != null) {
                    String safeId = idToken != null ? idToken.replace("'", "\\'") : "";
                    String safeAccess = accessToken != null ? accessToken.replace("'", "\\'") : "";
                    String js = "window.dispatchEvent(new CustomEvent('mediskye-native-google-auth', { detail: { idToken: '" + safeId + "', accessToken: '" + safeAccess + "' } }));";
                    bridge.getWebView().evaluateJavascript(js, null);
                }
            }
        });
    }

    @Override
    public void onResume() {
        super.onResume();
        if (pendingAuthIdToken != null || pendingAuthAccessToken != null) {
            final String id = pendingAuthIdToken;
            final String access = pendingAuthAccessToken;
            if (this.bridge != null && this.bridge.getWebView() != null) {
                this.bridge.getWebView().postDelayed(new Runnable() {
                    @Override
                    public void run() {
                        dispatchAuthTokensToWebView(id, access);
                    }
                }, 500);
            }
        }
    }

    @Override
    public void onBackPressed() {
        if (this.bridge != null && this.bridge.getWebView() != null) {
            final WebView webView = this.bridge.getWebView();
            webView.evaluateJavascript(
                "(function(){ return !!(window.__mediskyeHandleBack && window.__mediskyeHandleBack()); })()",
                value -> {
                    if ("true".equalsIgnoreCase(value)) {
                        // Handled by MediSkye React UI (closed open modal or drawer)
                        return;
                    }
                    if (webView.canGoBack()) {
                        webView.goBack();
                    } else {
                        MainActivity.super.onBackPressed();
                    }
                }
            );
            return;
        }
        super.onBackPressed();
    }

    private synchronized int startLoopbackServerIfNeeded() {
        if (activeLoopbackPort != 0 && serverSocket != null && !serverSocket.isClosed()) {
            return activeLoopbackPort;
        }

        try {
            serverSocket = new ServerSocket(0, 50, InetAddress.getByName("127.0.0.1"));
            activeLoopbackPort = serverSocket.getLocalPort();
            Log.i(TAG, "Started loopback server on port " + activeLoopbackPort);

            new Thread(new Runnable() {
                @Override
                public void run() {
                    while (serverSocket != null && !serverSocket.isClosed()) {
                        try {
                            final Socket client = serverSocket.accept();
                            try {
                                client.setSoTimeout(3000);
                            } catch (Exception ignored) {}
                            new Thread(new Runnable() {
                                @Override
                                public void run() {
                                    handleClientSocket(client);
                                }
                            }).start();
                        } catch (Exception e) {
                            if (serverSocket == null || serverSocket.isClosed()) {
                                break;
                            }
                            Log.w(TAG, "Loopback connection error: " + e.getMessage());
                        }
                    }
                }
            }).start();

            return activeLoopbackPort;
        } catch (Exception e) {
            Log.e(TAG, "Failed to start loopback server", e);
            return 0;
        }
    }

    private void handleClientSocket(Socket client) {
        try {
            InputStream in = client.getInputStream();
            OutputStream out = client.getOutputStream();

            byte[] buf = new byte[8192];
            int read = in.read(buf);
            if (read <= 0) {
                client.close();
                return;
            }

            String req = new String(buf, 0, read, StandardCharsets.UTF_8);
            String firstLine = req.split("\r\n")[0];
            String[] parts = firstLine.split("\\s+");
            if (parts.length < 2) {
                client.close();
                return;
            }

            String rawUri = parts[1];
            String path = rawUri;
            String query = "";
            int qIdx = rawUri.indexOf('?');
            if (qIdx >= 0) {
                path = rawUri.substring(0, qIdx);
                query = rawUri.substring(qIdx + 1);
            }

            if ("/__native_auth_done".equals(path)) {
                String idToken = "";
                String accessToken = "";
                for (String param : query.split("&")) {
                    String[] kv = param.split("=", 2);
                    if (kv.length == 2) {
                        String key = kv[0];
                        String val = URLDecoder.decode(kv[1], "UTF-8");
                        if ("id_token".equals(key)) {
                            idToken = val;
                        } else if ("access_token".equals(key)) {
                            accessToken = val;
                        }
                    }
                }

                // Immediately dispatch to UI thread
                dispatchAuthTokensToWebView(idToken, accessToken);

                // Bring MainActivity to the front
                Intent bringToFront = new Intent(MainActivity.this, MainActivity.class);
                bringToFront.setFlags(Intent.FLAG_ACTIVITY_REORDER_TO_FRONT | Intent.FLAG_ACTIVITY_SINGLE_TOP);
                startActivity(bringToFront);

                String intentUri = "intent://auth-callback?id_token=" + Uri.encode(idToken) + "&access_token=" + Uri.encode(accessToken) + "#Intent;scheme=mediskye;package=com.mediskye.app;end";

                String html = "<!DOCTYPE html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1.0'>"
                        + "<title>MediSkye — Signed In</title>"
                        + "<style>body{background-color:#070B14;color:#F8FAFC;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;text-align:center;}"
                        + ".card{background:rgba(15,23,42,0.9);border:1px solid rgba(56,189,248,0.3);border-radius:16px;padding:24px 32px;max-width:360px;}"
                        + "h2{margin:0 0 8px 0;color:#38BDF8;font-size:20px;}p{margin:0;color:#94A3B8;font-size:14px;}</style></head>"
                        + "<body><div class='card'><h2>Signed in to MediSkye!</h2><p>Returning to the application...</p></div>"
                        + "<script>"
                        + "setTimeout(function(){ window.location.href = '" + intentUri + "'; }, 200);"
                        + "setTimeout(function(){ try { window.close(); } catch(e){} }, 1000);"
                        + "</script></body></html>";

                byte[] htmlBytes = html.getBytes(StandardCharsets.UTF_8);
                String resp = "HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nContent-Length: " + htmlBytes.length + "\r\nConnection: close\r\n\r\n";
                out.write(resp.getBytes(StandardCharsets.UTF_8));
                out.write(htmlBytes);
                out.flush();
                client.close();
                return;
            }

            // Static asset serving from APK assets: public/<path>
            String assetPath = path.startsWith("/") ? path.substring(1) : path;
            if (assetPath.isEmpty()) {
                assetPath = "index.html";
            }

            InputStream assetIn = null;
            try {
                assetIn = getAssets().open("public/" + assetPath);
            } catch (Exception notFound) {
                try {
                    assetIn = getAssets().open("public/index.html");
                    assetPath = "index.html";
                } catch (Exception e) {
                    assetIn = null;
                }
            }

            if (assetIn == null) {
                String notFoundResp = "HTTP/1.1 404 Not Found\r\nContent-Length: 9\r\nConnection: close\r\n\r\nNot Found";
                out.write(notFoundResp.getBytes(StandardCharsets.UTF_8));
                out.flush();
                client.close();
                return;
            }

            ByteArrayOutputStream baos = new ByteArrayOutputStream();
            byte[] fileBuf = new byte[8192];
            int r;
            while ((r = assetIn.read(fileBuf)) != -1) {
                baos.write(fileBuf, 0, r);
            }
            assetIn.close();
            byte[] assetBytes = baos.toByteArray();

            String mimeType = "application/octet-stream";
            if (assetPath.endsWith(".html")) {
                mimeType = "text/html; charset=utf-8";
            } else if (assetPath.endsWith(".js") || assetPath.endsWith(".mjs")) {
                mimeType = "application/javascript";
            } else if (assetPath.endsWith(".css")) {
                mimeType = "text/css";
            } else if (assetPath.endsWith(".json")) {
                mimeType = "application/json";
            } else if (assetPath.endsWith(".svg")) {
                mimeType = "image/svg+xml";
            } else if (assetPath.endsWith(".png")) {
                mimeType = "image/png";
            } else if (assetPath.endsWith(".ico")) {
                mimeType = "image/x-icon";
            }

            String respHeader = "HTTP/1.1 200 OK\r\nContent-Type: " + mimeType + "\r\nContent-Length: " + assetBytes.length + "\r\nConnection: close\r\n\r\n";
            out.write(respHeader.getBytes(StandardCharsets.UTF_8));
            out.write(assetBytes);
            out.flush();
            client.close();
        } catch (Exception e) {
            Log.w(TAG, "Error handling client request: " + e.getMessage());
            try {
                client.close();
            } catch (Exception ignored) {}
        }
    }

    public class MediskyeNativeBridge {
        @JavascriptInterface
        public void startGoogleLogin() {
            runOnUiThread(new Runnable() {
                @Override
                public void run() {
                    int port = startLoopbackServerIfNeeded();
                    if (port == 0) {
                        Log.e(TAG, "Cannot launch external login: loopback server port is 0");
                        return;
                    }

                    Uri loginUri = Uri.parse("http://localhost:" + port + "/?native_google_auth=1");
                    Intent intent = new Intent(Intent.ACTION_VIEW, loginUri);
                    intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);

                    // Prefer Chrome if installed for optimal Google session sharing
                    PackageManager pm = getPackageManager();
                    Intent chromeIntent = new Intent(Intent.ACTION_VIEW, loginUri);
                    chromeIntent.setPackage("com.android.chrome");
                    chromeIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                    if (chromeIntent.resolveActivity(pm) != null) {
                        startActivity(chromeIntent);
                    } else {
                        startActivity(intent);
                    }
                }
            });
        }
    }
}

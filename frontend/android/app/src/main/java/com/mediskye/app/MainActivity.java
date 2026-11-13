package com.mediskye.app;

import android.annotation.SuppressLint;
import android.app.Dialog;
import android.content.DialogInterface;
import android.os.Bundle;
import android.os.Message;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.CookieManager;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import com.getcapacitor.BridgeActivity;
import com.getcapacitor.BridgeWebChromeClient;

public class MainActivity extends BridgeActivity {

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
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
            final String finalUserAgent = ua;
            settings.setUserAgentString(finalUserAgent);

            // Hardware-acceleration & overscroll optimization for 120 FPS
            webView.setLayerType(View.LAYER_TYPE_HARDWARE, null);
            webView.setOverScrollMode(View.OVER_SCROLL_NEVER);

            webView.setWebChromeClient(new BridgeWebChromeClient(this.bridge) {
                @Override
                public boolean onCreateWindow(WebView view, boolean isDialog, boolean isUserGesture, Message resultMsg) {
                    final Dialog dialog = new Dialog(MainActivity.this, android.R.style.Theme_Black_NoTitleBar_Fullscreen);
                    final WebView childWebView = new WebView(MainActivity.this);

                    WebSettings childSettings = childWebView.getSettings();
                    childSettings.setJavaScriptEnabled(true);
                    childSettings.setDomStorageEnabled(true);
                    childSettings.setDatabaseEnabled(true);
                    childSettings.setSupportMultipleWindows(true);
                    childSettings.setJavaScriptCanOpenWindowsAutomatically(true);
                    childSettings.setUserAgentString(finalUserAgent);

                    CookieManager.getInstance().setAcceptThirdPartyCookies(childWebView, true);

                    childWebView.setLayoutParams(new ViewGroup.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT,
                        ViewGroup.LayoutParams.MATCH_PARENT
                    ));

                    childWebView.setWebViewClient(new WebViewClient() {
                        @Override
                        public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest req) {
                            if (req != null && req.getUrl() != null) {
                                String scheme = req.getUrl().getScheme();
                                if ("http".equalsIgnoreCase(scheme) || "https".equalsIgnoreCase(scheme)) {
                                    return false; // Keep inside childWebView
                                }
                            }
                            return false;
                        }

                        @SuppressWarnings("deprecation")
                        @Override
                        public boolean shouldOverrideUrlLoading(WebView v, String url) {
                            if (url != null && (url.startsWith("http://") || url.startsWith("https://"))) {
                                return false;
                            }
                            return false;
                        }
                    });

                    childWebView.setWebChromeClient(new WebChromeClient() {
                        @Override
                        public void onCloseWindow(WebView window) {
                            try {
                                if (dialog.isShowing()) {
                                    dialog.dismiss();
                                }
                            } catch (Exception ignored) {}
                            try {
                                childWebView.destroy();
                            } catch (Exception ignored) {}
                        }
                    });

                    dialog.setCancelable(true);
                    dialog.setOnDismissListener(new DialogInterface.OnDismissListener() {
                        @Override
                        public void onDismiss(DialogInterface d) {
                            try {
                                childWebView.destroy();
                            } catch (Exception ignored) {}
                        }
                    });

                    dialog.setContentView(childWebView);
                    dialog.show();

                    WebView.WebViewTransport transport = (WebView.WebViewTransport) resultMsg.obj;
                    transport.setWebView(childWebView);
                    resultMsg.sendToTarget();
                    return true;
                }
            });
        }
    }
}

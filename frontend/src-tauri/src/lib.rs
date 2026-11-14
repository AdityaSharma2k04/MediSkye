use std::io::{Read, Write};
use std::net::TcpListener;
use std::sync::atomic::{AtomicU16, Ordering};
use tauri::{webview::NewWindowResponse, Manager, WebviewUrl, WebviewWindowBuilder};

static ACTIVE_PORT: AtomicU16 = AtomicU16::new(0);

fn percent_decode(s: &str) -> String {
  let mut bytes = Vec::new();
  let mut chars = s.bytes();
  while let Some(b) = chars.next() {
    if b == b'%' {
      let h1 = chars.next();
      let h2 = chars.next();
      if let (Some(c1), Some(c2)) = (h1, h2) {
        if let Ok(val) = u8::from_str_radix(
          &format!("{}{}", c1 as char, c2 as char),
          16,
        ) {
          bytes.push(val);
          continue;
        }
      }
    } else if b == b'+' {
      bytes.push(b' ');
      continue;
    }
    bytes.push(b);
  }
  String::from_utf8_lossy(&bytes).to_string()
}

fn start_loopback_server(app_handle: tauri::AppHandle) -> u16 {
  let current_port = ACTIVE_PORT.load(Ordering::SeqCst);
  if current_port != 0 {
    return current_port;
  }

  let listener = match TcpListener::bind("127.0.0.1:0") {
    Ok(l) => l,
    Err(e) => {
      eprintln!("[MediSkye Native Auth] Failed to bind loopback: {}", e);
      return 0;
    }
  };

  let port = match listener.local_addr() {
    Ok(addr) => addr.port(),
    Err(e) => {
      eprintln!("[MediSkye Native Auth] Failed to get local port: {}", e);
      return 0;
    }
  };

  ACTIVE_PORT.store(port, Ordering::SeqCst);

  let handle_clone = app_handle.clone();
  std::thread::spawn(move || {
    for stream_res in listener.incoming() {
      let mut stream = match stream_res {
        Ok(s) => s,
        Err(_) => continue,
      };

      let handle = handle_clone.clone();
      std::thread::spawn(move || {
        let _ = stream.set_read_timeout(Some(std::time::Duration::from_millis(3000)));
        let _ = stream.set_write_timeout(Some(std::time::Duration::from_millis(3000)));

        let mut buf = [0u8; 8192];
        let bytes_read = match stream.read(&mut buf) {
          Ok(n) => n,
          Err(_) => return,
        };
        if bytes_read == 0 {
          return;
        }

        let req_str = String::from_utf8_lossy(&buf[..bytes_read]);
        let first_line = req_str.lines().next().unwrap_or("");
        let parts: Vec<&str> = first_line.split_whitespace().collect();
        if parts.len() < 2 {
          return;
        }

        let raw_path = parts[1];
        let (path, query) = match raw_path.split_once('?') {
          Some((p, q)) => (p, q),
          None => (raw_path, ""),
        };

        if path == "/__native_auth_done" {
          let mut id_token = String::new();
          let mut access_token = String::new();
          for param in query.split('&') {
            if let Some((k, v)) = param.split_once('=') {
              if k == "id_token" {
                id_token = percent_decode(v);
              } else if k == "access_token" {
                access_token = percent_decode(v);
              }
            }
          }

          if let Some(main_win) = handle.get_webview_window("main") {
            let js = format!(
              "window.dispatchEvent(new CustomEvent('mediskye-native-google-auth', {{ detail: {{ idToken: {:?}, accessToken: {:?} }} }}));",
              id_token, access_token
            );
            let _ = main_win.eval(&js);
            let _ = main_win.unminimize();
            let _ = main_win.show();
            let _ = main_win.set_focus();
          }

          let body = r#"<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>MediSkye — Signed In</title>
  <style>
    body {
      background-color: #070B14;
      color: #F8FAFC;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      display: flex;
      align-items: center;
      justify-content: center;
      height: 100vh;
      margin: 0;
      text-align: center;
    }
    .card {
      background: rgba(15, 23, 42, 0.85);
      border: 1px solid rgba(56, 189, 248, 0.25);
      border-radius: 16px;
      padding: 32px 40px;
      max-width: 420px;
      box-shadow: 0 20px 40px rgba(0,0,0,0.5);
    }
    h2 { margin: 0 0 12px 0; color: #38BDF8; font-size: 20px; }
    p { margin: 0; color: #94A3B8; font-size: 14px; line-height: 1.5; }
  </style>
</head>
<body>
  <div class="card">
    <h2>Signed in to MediSkye!</h2>
    <p>Returning to the desktop application... You can safely close this browser tab.</p>
  </div>
  <script>
    setTimeout(function() {
      try { window.close(); } catch(e) {}
    }, 800);
  </script>
</body>
</html>"#;

          let response = format!(
            "HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}",
            body.len(),
            body
          );
          let _ = stream.write_all(response.as_bytes());
          let _ = stream.flush();
          return;
        }

        // Serve static frontend assets from Tauri asset resolver
        let mut asset_path = path.trim_start_matches('/');
        if asset_path.is_empty() {
          asset_path = "index.html";
        }

        let (content_type, asset_data) = match handle.asset_resolver().get(asset_path.to_string()) {
          Some(asset) => {
            let ct = asset.mime_type.to_string();
            (ct, asset.bytes.to_vec())
          }
          None => {
            // Fallback to index.html for SPA client-side routing
            match handle.asset_resolver().get("index.html".to_string()) {
              Some(fallback) => (
                "text/html; charset=utf-8".to_string(),
                fallback.bytes.to_vec(),
              ),
              None => (
                "text/plain".to_string(),
                b"Not Found".to_vec(),
              ),
            }
          }
        };

        let response_header = format!(
          "HTTP/1.1 200 OK\r\nContent-Type: {}\r\nContent-Length: {}\r\nConnection: close\r\n\r\n",
          content_type,
          asset_data.len()
        );
        let _ = stream.write_all(response_header.as_bytes());
        let _ = stream.write_all(&asset_data);
        let _ = stream.flush();
      });
    }
  });

  port
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
  tauri::Builder::default()
    .setup(|app| {
      let app_handle = app.handle().clone();
      let app_handle_for_window = app_handle.clone();

      WebviewWindowBuilder::new(app, "main", WebviewUrl::App("index.html".into()))
        .title("MediSkye — Clinical Lab Intelligence")
        .inner_size(1440.0, 900.0)
        .min_inner_size(390.0, 640.0)
        .resizable(true)
        .center()
        .background_color(tauri::window::Color(7, 11, 20, 255))
        .initialization_script(r#"
          window.MediskyeNativeAuth = {
            startGoogleLogin: function() {
              window.open('http://tauri.localhost/__start_external_google_login', '_blank');
            }
          };
        "#)
        .on_new_window(move |url, _features| {
          let url_str = url.as_str();
          if url_str.contains("__start_external_google_login")
            || url_str.contains("accounts.google.com")
            || url_str.contains("__/auth/handler")
          {
            let port = start_loopback_server(app_handle_for_window.clone());
            if port != 0 {
              let login_url = format!("http://localhost:{}/?native_google_auth=1", port);
              #[cfg(target_os = "windows")]
              {
                use std::os::windows::process::CommandExt;
                let _ = std::process::Command::new("cmd")
                  .args(["/C", "start", "", &login_url])
                  .creation_flags(0x08000000) // CREATE_NO_WINDOW
                  .spawn();
              }
              #[cfg(not(target_os = "windows"))]
              {
                let _ = std::process::Command::new("open").arg(&login_url).spawn();
              }
            }
            return NewWindowResponse::Deny;
          }
          NewWindowResponse::Allow
        })
        .build()?;
      Ok(())
    })
    .run(tauri::generate_context!())
    .expect("error while running MediSkye desktop application");
}

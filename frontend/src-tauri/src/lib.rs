use tauri::{webview::NewWindowResponse, WebviewUrl, WebviewWindowBuilder};

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
  tauri::Builder::default()
    .setup(|app| {
      WebviewWindowBuilder::new(app, "main", WebviewUrl::App("index.html".into()))
        .title("MediSkye — Clinical Lab Intelligence")
        .inner_size(1440.0, 900.0)
        .min_inner_size(390.0, 640.0)
        .resizable(true)
        .center()
        .on_new_window(|_url, _features| NewWindowResponse::Allow)
        .build()?;
      Ok(())
    })
    .run(tauri::generate_context!())
    .expect("error while running MediSkye desktop application");
}

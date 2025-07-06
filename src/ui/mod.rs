use wasm_bindgen::prelude::*;
use leptos::*;

#[wasm_bindgen]
pub fn start_web_ui() {
    mount_to_body(|cx| view! { cx, <UiRoot/> })
}

#[allow(non_snake_case)]
#[component]
fn UiRoot(cx: Scope) -> impl IntoView {
    let (metrics, set_metrics) = create_signal(cx, Metrics::default());
    
    spawn_local(async move {
        match WebSocket::connect("ws://localhost:8080/ui").await {
            Ok(ws) => {
                while let Ok(msg) = ws.recv().await {
                    if let Ok(parsed_metrics) = serde_json::from_str::<Metrics>(&msg) {
                        set_metrics.update(move |m| *m = parsed_metrics);
                    }
                }
            }
            Err(e) => logging::log!("WebSocket connection error: {:?}", e),
        }
    });
    
    view! { cx,
        <Dashboard metrics=metrics/>
        <ControlPanel/>
    }
}
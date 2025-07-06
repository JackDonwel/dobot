// build.rs
fn main() {
    println!("cargo:rustc-link-lib=javascriptcoregtk-4.1");
    println!("cargo:rustc-link-lib=webkit2gtk-4.1");
}
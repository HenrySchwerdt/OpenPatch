//! Builds the C reference core (firmware/core/src/*.c, never modified) plus our shim into a
//! static library that the host-only differential tests link against.
use std::path::PathBuf;

fn main() {
    let manifest = PathBuf::from(std::env::var("CARGO_MANIFEST_DIR").expect("manifest dir"));
    let core = manifest.join("../../firmware/core");
    let src = core.join("src");

    let mut build = cc::Build::new();
    build.std("c11").include(core.join("include")).include(manifest.join("csrc")).warnings(true);

    let mut files: Vec<PathBuf> = std::fs::read_dir(&src)
        .expect("firmware/core/src must exist")
        .filter_map(|e| e.ok().map(|e| e.path()))
        .filter(|p| p.extension().map(|x| x == "c").unwrap_or(false))
        .collect();
    files.sort();
    for f in &files {
        println!("cargo:rerun-if-changed={}", f.display());
        build.file(f);
    }
    println!("cargo:rerun-if-changed={}", core.join("include").display());
    println!("cargo:rerun-if-changed=csrc/shim.c");
    println!("cargo:rerun-if-changed=csrc/shim.h");
    build.file(manifest.join("csrc/shim.c"));
    build.compile("opcore_c_reference");
}

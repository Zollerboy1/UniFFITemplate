# UniFFITemplate

A simple template for integrating a Rust library into a Swift package using [UniFFI](https://mozilla.github.io/uniffi-rs).

## Usage

After you have cloned this repository, run the following command:

```bash
./util/build setup
```

This will let you configure your package interactively.

After the package is set up, you can build it like this:

```bash
./util/build
swift build
```

or

```bash
./util/build --release
swift build -c release
```

The build script will build the cargo package located at `Sources/<PROJECT_NAME>Rust/cargo`, generate the Swift bindings for it, and put them into the right place so that `swift build` can find them.

Every time you have changed something in the cargo package (while keeping the `.udl` file up to date), you have to use `./util/build` again, so that the changes become visible in the Swift bindings.

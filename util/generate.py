import argparse
import json
import os
import shutil

from utility import camel_to_snake, check_command


parser = argparse.ArgumentParser()

build_type = parser.add_mutually_exclusive_group()
build_type.add_argument('-d', '--debug', action='store_true', dest='debug', help='Build in debug mode')
build_type.add_argument('-r', '--release', action='store_false', dest='debug', help='Build in release mode')

parser.set_defaults(debug=True)


util_dir = os.path.dirname(os.path.realpath(__file__))
repo_dir = os.path.dirname(util_dir)

sources_dir = os.path.join(repo_dir, 'Sources')


def main(args: list[str]) -> int:
    parsed_args = parser.parse_args(args)

    os.chdir(repo_dir)
    if not check_command('swift', 'Swift', 'https://swift.org/getting-started/#installing-swift'):
        return 1
    if not check_command('cargo', 'Cargo', 'https://doc.rust-lang.org/cargo/getting-started/installation.html'):
        return 1
    if not check_command('uniffi-bindgen', 'uniffi-bindgen', 'https://mozilla.github.io/uniffi-rs/'):
        return 1
    if not check_command('xcrun', 'Xcode', 'https://developer.apple.com/xcode/'):
        return 1

    json_string = os.popen('swift package dump-package').read()
    json_dict = json.loads(json_string)
    project_name = json_dict['name']

    bindings_module_dir = os.path.join(sources_dir, project_name + 'Bindings')
    rust_module_dir = os.path.join(sources_dir, project_name + 'Rust')
    cargo_dir = os.path.join(rust_module_dir, 'cargo')
    include_dir = os.path.join(rust_module_dir, 'include')
    lib_dir = os.path.join(rust_module_dir, 'lib')
    swift_bindings_path = os.path.join(bindings_module_dir, project_name + 'Bindings.swift')
    c_bindings_path = os.path.join(include_dir, project_name + 'Rust.h')
    modulemap_path = os.path.join(include_dir, project_name + 'Rust.modulemap')
    xcframework_path = os.path.join(lib_dir, project_name + 'Rust.xcframework')

    project_name_snake = camel_to_snake(project_name)

    print('Generating bindings for Cargo project {}...'.format(project_name_snake))

    os.chdir(cargo_dir)

    if os.system('uniffi-bindgen generate --language swift --out-dir {} src/{}.udl'.format(include_dir, project_name_snake)) != 0:
        print('Failed to generate C and Swift bindings.')
        return 1

    os.rename(os.path.join(include_dir, project_name_snake + '.swift'), swift_bindings_path)
    os.rename(os.path.join(include_dir, project_name_snake + 'FFI.h'), c_bindings_path)
    os.rename(os.path.join(include_dir, project_name_snake + 'FFI.modulemap'), modulemap_path)

    with open(swift_bindings_path, 'r') as f:
        contents = f.read()
    contents = contents.replace(project_name_snake + 'FFI', project_name + 'CBindings')
    with open(swift_bindings_path, 'w') as f:
        f.write(contents)

    for path in [c_bindings_path, modulemap_path]:
        with open(path, 'r') as f:
            contents = f.read()
        contents = contents.replace(project_name_snake + 'FFI', project_name + 'Rust')
        with open(path, 'w') as f:
            f.write(contents)

    print('Successfully generated bindings for Cargo project {}.'.format(project_name_snake))

    print('Building Cargo project {}...'.format(project_name_snake))

    if os.system('cargo build{}'.format('' if parsed_args.debug else ' --release')) != 0:
        print('Failed to build Cargo project.')
        return 1

    print('Successfully built Cargo project {}.'.format(project_name_snake))

    print('Creating xcframework...')

    os.chdir(repo_dir)

    if os.path.exists(xcframework_path):
        shutil.rmtree(xcframework_path)

    if os.system('xcrun xcodebuild -create-xcframework -library {} -output {}'.format(os.path.join(cargo_dir, 'target', 'debug' if parsed_args.debug else 'release', 'lib' + project_name_snake + '.a'), xcframework_path)) != 0:
        print('Failed to create xcframework.')
        return 1

    print('Done.')

    return 0

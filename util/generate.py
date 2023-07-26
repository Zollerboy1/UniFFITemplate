import argparse
import json
import os
import shutil
import subprocess

from utility import camel_to_snake, check_command


parser = argparse.ArgumentParser()

build_type = parser.add_mutually_exclusive_group()
build_type.add_argument('-d', '--debug', action='store_true', dest='debug', help='Build in debug mode')
build_type.add_argument('-r', '--release', action='store_false', dest='debug', help='Build in release mode')

parser.add_argument('-u', '--universal', action='store_true', dest='universal', help='Build universal binary')

parser.set_defaults(debug=True, universal=False)


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
    if not check_command('xcrun', 'Xcode', 'https://developer.apple.com/xcode/'):
        return 1
    if parsed_args.universal:
        if not check_command('rustup', 'Rustup', 'https://rustup.rs/'):
            return 1
        target_list = [line.strip() for line in os.popen('rustup target list --installed').read().splitlines()]
        if 'aarch64-apple-darwin' not in target_list:
            print('The target aarch64-apple-darwin is not installed. Please install it before continuing.')
            print('You can install it using the following command: rustup target add aarch64-apple-darwin')
            return 1
        if 'x86_64-apple-darwin' not in target_list:
            print('The target x86_64-apple-darwin is not installed. Please install it before continuing.')
            print('You can install it using the following command: rustup target add x86_64-apple-darwin')
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

    target_dir_name = 'debug' if parsed_args.debug else 'release'

    project_name_snake = camel_to_snake(project_name)
    rust_lib_name = 'lib' + project_name_snake + '.a'

    print('Generating bindings for Cargo project {}...'.format(project_name_snake))

    os.chdir(cargo_dir)

    if os.system('cargo run --features=uniffi/cli --bin uniffi-bindgen generate --language swift --out-dir {} src/{}.udl'.format(include_dir, project_name_snake)) != 0:
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

    rust_target_dir = os.path.join(repo_dir, 'target')
    if not os.path.exists(rust_target_dir):
        rust_target_dir = os.path.join(cargo_dir, 'target')

    if parsed_args.universal:
        json_string = os.popen('xcodebuild -showsdks -json').read()
        sdk_list = sorted(([sdk['sdkPath'], sdk['platformVersion']] for sdk in json.loads(json_string) if sdk['platform'] == 'macosx'),
                          key=lambda sdk: int(sdk[1].split('.')[0]) * 100 + int(sdk[1].split('.')[1]))
        if len(sdk_list) == 0:
            print('No macOS SDKs found.')
            return 1

        sdk_path, platform_version = sdk_list[-1]
        architecture = os.popen('uname -m').read().strip()
        if architecture == 'arm64':
            target = 'x86_64-apple-darwin'
        elif architecture == 'x86_64':
            target = 'aarch64-apple-darwin'
        else:
            print('Unsupported architecture: {}'.format(architecture))
            return 1

        print('Building Cargo project {} for target {}...'.format(project_name_snake, target))

        env = os.environ.copy()
        env['SDKROOT'] = sdk_path
        env['MACOSX_DEPLOYMENT_TARGET'] = platform_version
        if subprocess.call('cargo build --target={}{}'.format(target, '' if parsed_args.debug else ' --release'),
                           shell=True,
                           env=env) != 0:
            print('Failed to build Cargo project for target {}.'.format(target))
            return 1

        print('Successfully built Cargo project {} for target {}.'.format(project_name_snake, target))

        universal_target_dir = os.path.join(rust_target_dir, 'universal-apple-darwin', target_dir_name)
        universal_lib_path = os.path.join(universal_target_dir, rust_lib_name)

        if not os.path.exists(universal_target_dir):
            os.makedirs(universal_target_dir)

        print('Creating universal binary...')

        if os.system('lipo -create -output {} {} {}'.format(universal_lib_path,
                        os.path.join(rust_target_dir, target_dir_name, rust_lib_name),
                        os.path.join(rust_target_dir, target, target_dir_name, rust_lib_name))) != 0:
            print('Failed to create universal binary.')
            return 1

        print('Successfully created universal binary.')

    print('Creating xcframework...')

    os.chdir(repo_dir)

    if os.path.exists(xcframework_path):
        shutil.rmtree(xcframework_path)

    if parsed_args.universal:
        built_lib_path = universal_lib_path
    else:
        built_lib_path = os.path.join(rust_target_dir, target_dir_name, rust_lib_name)
    if os.system('xcrun xcodebuild -create-xcframework -library {} -output {}'.format(built_lib_path, xcframework_path)) != 0:
        print('Failed to create xcframework.')
        return 1

    print('Done.')

    return 0

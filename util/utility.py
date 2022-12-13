import re

from shutil import which


def camel_to_snake(name: str) -> str:
    if name == 'UniFFITemplate':
        return 'uniffi_template'
    name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', name).lower()

def check_command(command: str, name: str, installation_instructions_url: str) -> bool:
    if which(command) is None:
        print('{} is not installed. Please install {} before continuing.'.format(name, name))
        print('Instructions for installing {} can be found here: {}'.format(name, installation_instructions_url))
        return False
    return True

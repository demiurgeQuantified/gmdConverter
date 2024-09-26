import os
import sys
import struct
import json
from typing import BinaryIO

SUPPORTED_VERSIONS = [195]
"""List of supported world versions."""
# TODO: a lot more versions than this are probably supported, gmd is a newer feature and may not have been changed ever


JSON_WORLD_VERSION_KEY = "__WORLD_VERSION"
"""Key for the world version in the json format."""
# keys have type prefixes, so they can always be converted back to the right type, as json only supports string keys
JSON_NUMBER_PREFIX = "_number: "
"""Prefix for number keys."""
JSON_STRING_PREFIX = "_string: "
"""Prefix for string keys."""


type luaTable = dict[str | float, str | float | bool | luaTable]


class GlobalModData:
    def __init__(self, world_version: int):
        self.world_version: int = world_version
        """Version of the world."""
        self.tables: dict[str, luaTable] = {}
        """Global mod data tables by their string keys."""


def table_keys_to_json(table: luaTable) -> luaTable:
    result = {}
    for key, value in table.items():
        if type(key) is str:
            key = JSON_STRING_PREFIX + key
        elif type(key) is float:
            key = JSON_NUMBER_PREFIX + str(key)

        if type(value) is dict:
            value = table_keys_to_json(value)
        result[key] = value

    return result


def table_keys_from_json(table: luaTable) -> luaTable:
    result = {}
    for key, value in table.items():
        if type(key) is str:
            if key.startswith(JSON_STRING_PREFIX):
                key = key.removeprefix(JSON_STRING_PREFIX)
            elif key.startswith(JSON_NUMBER_PREFIX):
                key = float(key.removeprefix(JSON_NUMBER_PREFIX))

        if type(value) is dict:
            value = table_keys_from_json(value)
        result[key] = value

    return result


def read_int(file: BinaryIO) -> int:
    return int.from_bytes(file.read(4), 'big', signed=False)


def write_int(file: BinaryIO, num: int):
    file.write(num.to_bytes(4, 'big', signed=False))


def read_bool(file: BinaryIO) -> bool:
    byte = file.read(1)
    if byte != b'\00' and byte != b'\01':
        raise Exception("Bool value is neither true or false")
    return byte != b'\00'


def write_bool(file: BinaryIO, value: bool):
    file.write(b'\01' if value else b'\00')


def read_double(file: BinaryIO) -> float:
    [f] = struct.unpack('!d', file.read(8))
    return f


def write_double(file: BinaryIO, num: float):
    file.write(struct.pack('!d', num))


def read_short(file: BinaryIO) -> int:
    return int.from_bytes(file.read(2), 'big', signed=False)


def write_short(file: BinaryIO, num: int):
    file.write(num.to_bytes(2, 'big', signed=False))


def read_string_utf8(file: BinaryIO, length: int | None = None) -> str:
    if length is None:
        length = read_short(file)
    return file.read(length).decode('utf-8')


def write_string_utf8(file: BinaryIO, string: str):
    write_short(file, len(string))
    file.write(string.encode('utf-8'))


def read_table(file: BinaryIO) -> luaTable:
    table = {}
    num_pairs = read_int(file)
    for i in range(num_pairs):
        key: str | float
        key_type = int.from_bytes(file.read(1))
        match key_type:
            case 0:  # string
                key = read_string_utf8(file)
            case 1:  # double
                key = read_double(file)
            case _:
                raise Exception("Invalid key type in table")

        value_type = int.from_bytes(file.read(1))
        match value_type:
            case 0:  # string
                table[key] = read_string_utf8(file)
            case 1:  # double
                table[key] = read_double(file)
            case 2:  # table
                table[key] = read_table(file)
            case 3:  # bool
                table[key] = read_bool(file)
            case _:
                raise Exception(f"Invalid value type (key {key})")

    return table


def write_table(file: BinaryIO, table: luaTable):
    write_int(file, len(table))
    for key, value in table.items():
        if type(key) is float:
            file.write(b'\01')
            write_double(file, key)
        elif type(key) is str:
            file.write(b'\00')
            write_string_utf8(file, key)
        else:
            raise Exception(f"Cannot write table key of type {type(key)}")

        if type(value) is str:
            file.write(b'\00')
            write_string_utf8(file, value)
        elif type(value) is float:
            file.write(b'\01')
            write_double(file, value)
        elif type(value) is dict:
            file.write(b'\02')
            write_table(file, value)
        elif type(value) is bool:
            file.write(b'\03')
            write_bool(file, value)
        else:
            raise Exception(f"Cannot write table value of type {type(value)} (Key : {key})")


def from_bin(filepath: str) -> GlobalModData:
    """
    Creates GlobalModData from a global mod data binary.
    :param filepath: Filepath of the binary to convert
    :return: the GlobalModData in the file
    """
    file = open(filepath, 'rb')

    world_version = read_int(file)
    if world_version not in SUPPORTED_VERSIONS:
        raise Exception(f"Unsupported world version {world_version}")
    global_mod_data = GlobalModData(world_version)

    num_entries = read_int(file)
    for i in range(num_entries):
        length = read_int(file)  # TODO maybe use this for error checking

        name = read_string_utf8(file)
        global_mod_data.tables[name] = read_table(file)
    file.close()

    return global_mod_data


def to_bin(filepath: str, gmd: GlobalModData):
    """
    Writes GlobalModData as a global mod data binary used by the game.
    :param filepath: The filepath to write to
    :param gmd: The GlobalModData to write
    :return:
    """
    file = open(filepath, 'wb')
    write_int(file, gmd.world_version)

    write_int(file, len(gmd.tables))  # number of keys
    for table_name, table in gmd.tables.items():
        start = file.tell()
        write_int(file, 0)  # leaves space to add the size later
        write_string_utf8(file, table_name)

        write_table(file, table)

        end = file.tell()
        file.seek(start)
        write_int(file, end - start - 4)
        file.seek(end)


def from_json(filepath: str) -> GlobalModData:
    """
    Creates GlobalModData from a JSON file.
    :param filepath: Filepath of a JSON file
    :return: the GlobalModData represented by the file
    """
    file = open(filepath, 'r')
    gmd_dict: dict = json.load(file)
    file.close()
    gmd = GlobalModData(gmd_dict[JSON_WORLD_VERSION_KEY])
    gmd_dict.pop(JSON_WORLD_VERSION_KEY)
    gmd.tables = table_keys_from_json(gmd_dict)
    return gmd


def to_json(filepath: str, gmd: GlobalModData):
    """
    Writes GlobalModData as a readable/editable JSON file. Keys will be prefixed with their type to ensure they can be
    converted back properly.
    :param filepath: The filepath to write to
    :param gmd: The GlobalModData to write
    :return:
    """
    gmd_dict = table_keys_to_json(gmd.tables)
    gmd_dict[JSON_WORLD_VERSION_KEY] = gmd.world_version

    file = open(filepath, 'w')
    json.dump(gmd_dict, file, indent=4)
    file.close()


def main():
    if len(sys.argv) < 2:
        print("No filepath passed.")
        exit(1)
    in_filepath = sys.argv[1]
    in_filepath = in_filepath.replace('\\', '/')
    extension = in_filepath.rsplit('/')[-1].rsplit('.', 1)[-1]

    out_filepath = sys.argv[2] if len(sys.argv) > 2 else None
    if extension == 'bin':
        gmd = from_bin(in_filepath)

        if out_filepath is None:
            out_filepath = "out/global_mod_data.json"
        os.makedirs(out_filepath.rsplit('/')[0], exist_ok=True)

        to_json(out_filepath, gmd)
    elif extension == 'json':
        gmd = from_json(in_filepath)

        if out_filepath is None:
            out_filepath = "out/global_mod_data.bin"
        os.makedirs(out_filepath.rsplit('/')[0], exist_ok=True)

        to_bin(out_filepath, gmd)
    else:
        print("Invalid file extension. Pass a .bin file to convert to json, or pass a .json file to convert to bin.")


if __name__ == "__main__":
    main()

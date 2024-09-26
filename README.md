# Global Mod Data Converter
A python script to convert Project Zomboid global mod data binaries to and from JSON, so that they can be viewed and edited easily.
## Usage
1. Install [Python](https://www.python.org/downloads/) 3.12 or above.
2. Clone the repository, or download from [Releases](/releases/latest/).
3. Run ``python gmd_converter.py in_filepath out_filepath``.
   
``in_filepath`` should be the path to the input file. A file with the extension ``.bin`` will be converted to JSON, and a file with the extension ``.json`` will be converted to global mod data binary.

``out_filepath`` is the optional path to write the output to. If you pass nothing the output will be written to ``out/global_mod_data``.
## JSON details
All table keys will be prefixed with ``_string: `` or ``_number: ``. This is to preserve their type, as JSON does not support non-string keys.

An additional key ``__WORLD_VERSION`` is created - this is not a global mod data entry, it is simply metadata.

"""Constants shared by the Vertiv Unity plug-in and the command line tools in tools/.

This module must not import anything from Checkmk (cmk): the tools run without a Checkmk installation.
"""

# Base OID of the LIEBERT-GP-FLEXIBLE-MIB tables (lgpFlexibleBasicTable and its siblings)
FLEX_BASE = ".1.3.6.1.4.1.476.1.42.3.9"

# lgpFlexibleEntryDataType
TYPE_NAMES = {
    0: "not specified", 1: "int16", 2: "uint16", 3: "int32", 4: "uint32", 5: "text",
    6: "enum", 7: "event16", 8: "event32", 9: "ipv4", 10: "time32",
}

# lgpFlexibleEntryAccessibility
ACCESS_NAMES = {0: "not specified", 1: "read-only", 2: "write-only", 3: "read-write"}

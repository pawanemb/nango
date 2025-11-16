from enum import Enum

class GenderEnum(str, Enum):
    MALE = "MALE"
    FEMALE = "FEMALE"
    NON_BINARY = "NON-BINARY"
    ALL = "ALL"
    OTHERS = "OTHERS"

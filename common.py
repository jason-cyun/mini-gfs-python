# Configs and common utils

from dataclasses import dataclass
import enum


class Config:
    chunk_size: int = 4
    master_loc: str = "60051"
    chunkserver_locs: list = ["60052", "60053", "60054", "60055", "60056", "60057"]
    chunkserver_root: str = "root_chunkserver"  # root dir in chunk server


class Status:
    def __init__(self, v, e) -> None:
        self.v = v
        self.e = e
        if self.e:
            print(self.e)


def isInt(e):
    try:
        e = int(e)
    except:
        return False
    else:
        return True


class HeartBeatStatus(enum.Enum):
    ok = "SERVING"
    error = "NOT_SEVING"
    unknown = "UNKNOWN"  # not currently used

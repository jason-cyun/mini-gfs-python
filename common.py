# Configs and common utils

from dataclasses import dataclass
import enum


class Config:
    chunk_size: int = 4
    master_loc: str = "50051"
    chunkserver_locs: list = ["50052", "50053", "50054", "50055", "50056"]
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

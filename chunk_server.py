""" chunk server methods 
Runs the servers as different processes and each server has 3 workers (threads) 
"""

import os
import sys
import time
from concurrent import futures
from multiprocessing import Pool, Process

import grpc
import gfs_pb2_grpc
import gfs_pb2

from common import Config, Status

class ChunkServer:
    """
    A chunk is a file in this case
    """
    def __init__(self, port, root) -> None:
        self.port = port
        self.root = root
        if not os.path.isdir(self.root):
            os.mkdir(self.root)

    def create(self, chunk_handle):
        try:
            # TODO: better way to make a file
            open(os.path.join(self.root, chunk_handle), 'w').close()

        except Exception as e:
            return Status(-1, f"ERROR : {e}")

        else:
            return Status(0, "SUCCESS : chunk created")

    def get_chunk_space(self, chunk_handle) -> tuple[int, Status]:
        try:
            chunk_space = str(Config.chunk_size - os.stat(os.path.join(self.root, chunk_handle)).st_size)

        except Exception as e:
            return None, Status(-1, f"ERROR : {e}")
        else:
            return chunk_space, Status(0, "")


    def append(self, chunk_handle, data) -> Status:
        try:
            with open(os.path.join(self.root, chunk_handle), "a") as f:
                f.write(data)
        except Exception as e:
            return Status(-1, f"ERROR : {e}")
        else:
            return Status(0, "SUCCESS : data appended")

    def read(self, chunk_handle, start_offset, numbytes) -> Status:
        start_offset = int(start_offset)
        numbytes = int(numbytes)
        try:
            with open(os.path.join(self.root, chunk_handle), "r") as f:
                f.seek(start_offset)
                ret = f.read(numbytes)
        except Exception as e:
            return Status(-1, f"ERROR : {e}")

        else:
            return Status(0, ret)

class ChunkServerToClientServicer(gfs_pb2_grpc.ChunkServerToClientServicer):
    def __init__(self, ckser : ChunkServer) -> None:
        self.ckser = ckser
        self.port = self.ckser.port

    def Create(self, request, context):
        chunk_handle = request.st
        print(f"{self.port} CreateChunk {chunk_handle}") #TODO: use logger
        status: Status = self.ckser.create(chunk_handle)
        return gfs_pb2.String(st=status.e)

    def GetChunkSpace(self, request, context):
        chunk_handle = request.st
        print(f"{self.port} GetChunkSpace {chunk_handle}")
        chunk_space, status = self.ckser.get_chunk_space(chunk_handle)
        if status.v != 0:
            return gfs_pb2.String(st=status.e)
        else:
            return gfs_pb2.String(st=chunk_space)

    def Append(self, request, context):
        chunk_handle, data = request.st.split("|")
        print(f"{self.port} Append {chunk_handle} {data}")
        status = self.ckser.append(chunk_handle, data)
        return gfs_pb2.String(st=status.e)

    def Read(self, request, context):
        chunk_handle, start_offset, numbytes = request.st.split("|")
        print(f"{chunk_handle} Read {start_offset} {numbytes}")
        status = self.ckser.read(chunk_handle, start_offset, numbytes)
        return gfs_pb2.String(st=status.e)

def start(port):
    """ Starts a single server (process with 3 worker) """

    print(f"Starting Chunk server on {port}")
    ckser = ChunkServer(port=port, root=os.path.join(Config.chunkserver_root, port))
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=3))
    gfs_pb2_grpc.add_ChunkServerToClientServicer_to_server(ChunkServerToClientServicer(ckser), server)
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    try:
        while True:
            time.sleep(200000)
    except KeyboardInterrupt:
        server.stop(0)

if __name__ == "__main__":
    for loc in Config.chunkserver_locs:
        p = Process(target=start, args=(loc,))
        p.start()
    p.join()
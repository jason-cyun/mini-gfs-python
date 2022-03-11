""" chunk server methods 
Runs the servers as different processes and each server has 3 workers (threads) 
"""

from http import client
import os
from pydoc import cli
import re
import sys
import time
from concurrent import futures
from multiprocessing import Pool, Process
from collections import defaultdict

import grpc
import gfs_pb2_grpc
import gfs_pb2

from common import Config, Status, HeartBeatStatus
from master_server import serve


class ChunkServer:
    """
    A chunk is a file in this case
    """

    def __init__(self, port, root) -> None:
        self.port = port
        self.root = root
        self.lease = -1  # in epoch time
        # TODO do we actually need a dict? I think a string should be just fine
        self.client2data = defaultdict(
            list
        )  # store data sent by the client TODO: garbage collection
        if not os.path.isdir(self.root):
            os.mkdir(self.root)

    def create(self, chunk_handle):
        try:
            # TODO: better way to make a file
            open(os.path.join(self.root, chunk_handle), "w").close()

        except Exception as e:
            return Status(-1, f"ERROR : {e}")

        else:
            return Status(0, "SUCCESS : chunk created")

    def get_chunk_space(self, chunk_handle) -> tuple[int, Status]:
        try:
            chunk_space = str(
                Config.chunk_size
                - os.stat(os.path.join(self.root, chunk_handle)).st_size
            )

        except Exception as e:
            return None, Status(-1, f"ERROR : {e}")
        else:
            return chunk_space, Status(0, "")

    def _append(self, chunk_handle, data) -> Status:
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

    def check(self, lease) -> str:
        """TODO add system/service check"""
        self.lease = int(lease)
        if self.lease != -1:
            print(f"chuckserver loc {self.port} is the primary")
        return "SERVING"

    def addData(self, clientid, data):
        self.client2data[clientid].append(data)
        return Status(0, "Added data to the chunk cache")

    def append(self, clientid):
        try:
            dataFrmClient = self.client2data[clientid]
            if not dataFrmClient:
                return Status(-1, "Data not found locally")
            chunk_handle, data = dataFrmClient[0].split("|")
            status = self._append(chunk_handle, data)
            return status

        except Exception as e:
            return Status(-1, f"Error {e}")


class ChunkServerToClientServicer(gfs_pb2_grpc.ChunkServerToClientServicer):
    def __init__(self, ckser: ChunkServer) -> None:
        self.ckser = ckser
        self.port = self.ckser.port

    def Create(self, request, context):
        chunk_handle = request.st
        print(f"{self.port} CreateChunk {chunk_handle}")  # TODO: use logger
        status: Status = self.ckser.create(chunk_handle)
        return gfs_pb2.String(st=status.e)

    def GetChunkSpace(self, request, context):
        chunk_handle = request.st
        print(f"{self.port} GetChunkSpace {chunk_handle}")
        chunk_space, status = self.ckser.get_chunk_space(chunk_handle)
        if status.v != 0:
            return gfs_pb2.String(st=status.e)
        else:
            return gfs_pb2.String(st=str(chunk_space))

    def Append(self, request, context):
        """Keeping this function in case we want to test out clint directly asking chunks to append"""
        # print("Wrong append call")
        # chunk_handle, data = request.st.split("|")
        # print(f"{self.port} Append {chunk_handle} {data}")
        # status = self.ckser.append(chunk_handle, data)
        # return gfs_pb2.String(st=status.e)
        clientid = request.st

        clientdata = self.ckser.client2data[clientid]
        print(f"clinetdata is {clientdata}")
        chunk_handle, data = clientdata[0].split("|")
        print(f"{self.port} Append {chunk_handle} {data}")
        status = self.ckser.append(clientid=clientid)
        return gfs_pb2.String(st=str(status.v))

    def Read(self, request, context):
        chunk_handle, start_offset, numbytes = request.st.split("|")
        print(f"{chunk_handle} Read {start_offset} {numbytes}")
        status = self.ckser.read(chunk_handle, start_offset, numbytes)
        return gfs_pb2.String(st=status.e)

    def AddData(self, request, context):
        clientid, data = request.st.split("||")
        chunk_handle, dataFrmClient = data.split("|")
        chunk_space, status = self.ckser.get_chunk_space(chunk_handle)
        if int(chunk_space)<len(dataFrmClient):
            # not enough chunkspace
            status = Status(-1, "-1 ERROR : Not enough chunk space")
            return gfs_pb2.String(st=status.e)
        status = self.ckser.addData(clientid, data)
        print(f"Locally stored data for clientid {clientid} : data {data}")
        return gfs_pb2.String(st=status.e)


class PrimaryToClientServicer(gfs_pb2_grpc.PrimaryToClientServicer):
    def __init__(self, ckser: ChunkServer) -> None:
        self.ckser = ckser
        self.port = self.ckser.port

    def Commit(self, request, context):
        """
        gets clientid and locs of other
        eg 1h23h2|123*234*234

        returns 0: success
        returns -1: fail
        returns -2: not the primary

        """

        cur_time = time.time()
        if cur_time > self.ckser.lease:
            return gfs_pb2.String(st="-2 Not Primary")

        clientid, locs = request.st.split("|")
        locs = locs.split("*")
        status = 0
        print(f"Primary {self.port} appending data to itself")
        status += self.ckser.append(clientid).v

        for loc in locs:
            chunk_addr = f"localhost:{loc}"
            with grpc.insecure_channel(chunk_addr) as channel:
                stub = gfs_pb2_grpc.ChunkServerToClientStub(channel)
                request = gfs_pb2.String(st=clientid)
                resp = stub.Append(request).st
                status += int(resp)

                print(f"Response from chunk server {loc} : {resp}")

        if status != 0:
            ret = gfs_pb2.String(st="-1 ERROR : all chunks did not commit")
        else:
            ret = gfs_pb2.String(st="0 SUCCESS : data appended")

        return ret


class HealthServicer(gfs_pb2_grpc.HealthServicer):
    def __init__(self, ckser: ChunkServer) -> None:
        self.ckser = ckser
        self.port = self.ckser.port

    def Check(self, request, context):
        lease = request.lease
        status = self.ckser.check(lease)
        if status == "SERVING":
            # print(gfs_pb2.HealthCheckResponse(status=status))
            return gfs_pb2.HealthCheckResponse(status=status)
        return gfs_pb2.HealthCheckResponse(status=HeartBeatStatus.error)


def start(port):
    """Starts a single server (process with 3 worker)"""
    # makes a base root dir which will have the dirs for each chunk server
    if not os.path.isdir(Config.chunkserver_root):
        os.mkdir(Config.chunkserver_root)

    print(f"Starting Chunk server on {port}")
    ckser = ChunkServer(port=port, root=os.path.join(Config.chunkserver_root, port))
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=3))
    gfs_pb2_grpc.add_ChunkServerToClientServicer_to_server(
        ChunkServerToClientServicer(ckser), server
    )
    gfs_pb2_grpc.add_HealthServicer_to_server(HealthServicer(ckser), server)
    gfs_pb2_grpc.add_PrimaryToClientServicer_to_server(
        PrimaryToClientServicer(ckser), server
    )
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

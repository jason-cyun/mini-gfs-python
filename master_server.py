import grp
import string
import time
import uuid
import random
from concurrent import futures
from collections import OrderedDict

import grpc
import gfs_pb2_grpc
import gfs_pb2

from common import Config, Status


def choose_locs() -> list:
    """Choose 3 locs randomly"""
    total = len(Config.chunkserver_locs)
    st = random.randint(0, total - 1)
    return [
        Config.chunkserver_locs[st],
        Config.chunkserver_locs[(st + 1) % total],
        Config.chunkserver_locs[(st + 2) % total],
    ]


class Chunk:
    def __init__(self) -> None:
        self.locs = []


class File:
    def __init__(self, file_path: str) -> None:
        """Since a file can be broken in multiple parts, it can be in different chunks"""
        self.file_path = file_path
        self.chunks: dict[str, Chunk] = OrderedDict()


class MetaData:
    def __init__(self) -> None:
        self.locs = Config.chunkserver_locs
        self.files: dict[str, File] = {}
        # chunk handle to file pointer
        self.ch2fp = {}

        self.locs_dict = {cs: [] for cs in self.locs}

    def get_latest_chunk(self, file_path):
        latest_chunk_handle = list(self.files[file_path].chunks.keys())[-1]
        return latest_chunk_handle

    def get_chunk_locs(self, chunk_handle) -> list:
        """get the chunk locs for a chunk handle"""
        file_path = self.ch2fp[chunk_handle]
        return self.files[file_path].chunks[chunk_handle].locs

    def create_new_file(self, file_path, chunk_handle) -> Status:
        if file_path in self.files:
            return Status(-1, f"ERROR : File exists already: {file_path}")
        fl = File(file_path)
        self.files[file_path] = fl
        status = self.create_new_chunk(file_path, -1, chunk_handle)
        return status

    def _check_health(self, chunkserver_addr, lease) -> string:
        """Piggybacking the lease time with the heatbeat message"""
        with grpc.insecure_channel(chunkserver_addr) as channel:
            stub = gfs_pb2_grpc.HealthStub(channel)
            req = gfs_pb2.HealthCheckRequest(lease=str(lease))
            cs_resp = stub.Check(req).status
        return cs_resp

    def check_health_all_loc(self, locs):
        """sets the 0th loc as primary. Does not actually change the loc if health is not good"""
        for i, loc in enumerate(locs):
            chunkserver_addr = f"localhost:{loc}"
            lease = -1
            if i == 0:
                # 0th index is the primary which gets a 60 sec lease
                lease = str(int(time.time()) + 60)

            heartbeat_msg = self._check_health(chunkserver_addr, lease)

            print(f"HeartBeat msg from {loc} : Status {heartbeat_msg}")

    def create_new_chunk(self, file_path, prev_chunk_handle, chunk_handle) -> Status:
        if file_path not in self.files:
            return Status(-2, f"ERROR : New chunk file does not exist: {file_path}")

        latest_chunk = None
        if prev_chunk_handle != -1:
            "file > 1 chunk"
            latest_chunk = self.get_latest_chunk(file_path)

            # Chunk already created
            if latest_chunk != prev_chunk_handle:
                return Status(
                    -3, f"ERROR : New chunk already created {file_path} {chunk_handle}"
                )

        chunk = Chunk()
        self.files[file_path].chunks[chunk_handle] = chunk
        locs = choose_locs()

        # TODO: change the server if status is not found or NOT_SERVING, currently it just leases the primary
        self.check_health_all_loc(locs)
        # for i, loc in enumerate(locs):
        #     chunkserver_addr = f"localhost:{loc}"
        #     lease = -1
        #     if i == 0:
        #         # 0th index is the primary which gets a 60 sec lease
        #         lease = str(int(time.time()) + 60)

        #     heartbeat_msg = self._check_health(chunkserver_addr, lease)

        #     print(f"HeartBeat msg from {loc} : Status {heartbeat_msg}")

        for loc in locs:
            self.locs_dict[loc].append(chunk_handle)
            self.files[file_path].chunks[chunk_handle].locs.append(loc)

        self.ch2fp[chunk_handle] = file_path
        return Status(0, "New Chunk Created")


class MasterServer:
    def __init__(self) -> None:
        self.file_list = ["/file1", "/file2", "/dir1/file3"]
        self.meta = MetaData()

    def get_chunk_handle(self):
        return str(uuid.uuid1())

    def get_available_chunk_servers(self):
        """TODO"""
        raise NotImplementedError

    def check_valid_file(self, file_path):
        if file_path not in self.meta.files:
            return Status(-1, "ERROR: file {} doesn't exist".format(file_path))
        else:
            return Status(0, "SUCCESS: file {} exists".format(file_path))

    def list_files(self, file_path):
        file_list = []
        for fp in self.meta.files.keys():
            if fp.startswith(file_path):
                file_list.append(fp)
        return file_list

    def create_file(self, file_path):
        chunk_handle = self.get_chunk_handle()
        status = self.meta.create_new_file(file_path, chunk_handle)

        if status.v != 0:
            return None, None, status

        locs = self.meta.files[file_path].chunks[chunk_handle].locs
        self.meta.check_health_all_loc(locs)
        return chunk_handle, locs, status

    def append_file(self, file_path) -> tuple[str, list, Status]:
        status = self.check_valid_file(file_path)

        if status.v != 0:
            return None, None, Status

        latest_chunk_handle = self.meta.get_latest_chunk(file_path)
        locs = self.meta.get_chunk_locs(latest_chunk_handle)
        # checks health ands sets primary
        self.meta.check_health_all_loc(locs)

        status = Status(0, "Append Handled")
        return latest_chunk_handle, locs, status

    def create_chunk(self, file_path, prev_chunk_handle):
        chunk_handle = self.get_chunk_handle()
        status = self.meta.create_new_chunk(file_path, prev_chunk_handle, chunk_handle)
        locs = self.meta.files[file_path].chunks[chunk_handle].locs
        return chunk_handle, locs, status

    def read_file(self, file_path, offset, numbytes):
        status = self.check_valid_file(file_path)
        if status.v != 0:
            return status

        chunk_size = Config.chunk_size
        start_chunk = offset // chunk_size
        all_chunks = list(self.meta.files[file_path].chunks.keys())
        if start_chunk > len(all_chunks):
            return Status(-1, "ERROR: Offset is too large")

        start_offset = offset % chunk_size

        if numbytes == -1:
            end_offset = chunk_size
            end_chunk = len(all_chunks) - 1
        else:
            end_offset = offset + numbytes - 1
            end_chunk = end_offset // chunk_size
            end_offset = end_offset % chunk_size

        all_chunk_handles = all_chunks[start_chunk : end_chunk + 1]
        ret = []
        for idx, chunk_handle in enumerate(all_chunk_handles):
            if idx == 0:
                stof = start_offset
            else:
                stof = 0
            if idx == len(all_chunk_handles) - 1:
                enof = end_offset
            else:
                enof = chunk_size - 1
            loc = self.meta.files[file_path].chunks[chunk_handle].locs[0]
            ret.append(
                chunk_handle + "*" + loc + "*" + str(stof) + "*" + str(enof - stof + 1)
            )
        ret = "|".join(ret)
        return Status(0, ret)


class MasterServerToClientServicer(gfs_pb2_grpc.MasterServerToClientServicer):
    def __init__(self, master: MasterServer) -> None:
        self.master = master

    def ListFiles(self, request, context) -> gfs_pb2.String:
        file_path = request.st
        print(f"Command ListFiles {file_path}")
        fpls = self.master.list_files(file_path)
        st = "|".join(fpls)
        return gfs_pb2.String(st=st)

    def CreateFile(self, request, context):
        file_path = request.st
        print(f"Command Create {file_path}")
        chunk_handle, locs, status = self.master.create_file(file_path)

        if status.v != 0:
            return gfs_pb2.String(st=status.e)

        st = chunk_handle + "|" + "|".join(locs)
        return gfs_pb2.String(st=st)

    def AppendFile(self, request, context):
        file_path = request.st
        print(f"Command Append {file_path}")
        latest_chunk_handle, locs, status = self.master.append_file(file_path)

        if status.v != 0:
            return gfs_pb2.String(st=status.e)

        st = latest_chunk_handle + "|" + "|".join(locs)
        return gfs_pb2.String(st=st)

    def CreateChunk(self, request, context):
        """returns: chunk_handle|127.0.0.1|127.0.0.1|127.0.0.1"""
        file_path, prev_chunk_handle = request.st.split("|")
        print(f"Command CreateChunk {file_path} {prev_chunk_handle}")
        chunk_handle, locs, status = self.master.create_chunk(
            file_path, prev_chunk_handle
        )
        # TODO: check status
        st = chunk_handle + "|" + "|".join(locs)
        return gfs_pb2.String(st=st)

    def ReadFile(self, request, context):
        file_path, offset, numbytes = request.st.split("|")
        print(f"Command ReadFile {file_path} {offset} {numbytes}")
        status = self.master.read_file(file_path, int(offset), int(numbytes))
        return gfs_pb2.String(st=status.e)


def serve():
    master = MasterServer()

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=3))
    gfs_pb2_grpc.add_MasterServerToClientServicer_to_server(
        MasterServerToClientServicer(master=master), server
    )
    # TODO get port from config
    server.add_insecure_port("[::]:60051")
    server.start()
    try:
        while True:
            time.sleep(2000)
    except KeyboardInterrupt:
        server.stop(0)


if __name__ == "__main__":
    serve()

import uuid
import sys
from turtle import st
from urllib import request

import grpc
import gfs_pb2
import gfs_pb2_grpc

from common import Config, isInt


def list_files(file_path):
    master = f"localhost:{Config.master_loc}"
    with grpc.insecure_channel(master) as channel:
        stub = gfs_pb2_grpc.MasterServerToClientStub(channel)
        request = gfs_pb2.String(st=file_path)
        master_response: str = stub.ListFiles(request).st
        fps = master_response.split("|")
        print(fps)


def create_file(file_path):
    """TODO: Will the primary create the file or client?
    It makes sense for the client to directly command the chunks to make the files since making a file is idempotent
    """
    master = f"localhost:{Config.master_loc}"
    with grpc.insecure_channel(master) as channel:
        stub = gfs_pb2_grpc.MasterServerToClientStub(channel)
        request = gfs_pb2.String(st=file_path)
        master_response: str = stub.CreateFile(request).st
        print(f"Response from master: {master_response}")

    if master_response.startswith("ERROR"):
        return -1

    data = master_response.split("|")
    chunk_handle = data[0]
    for loc in data[1:]:
        chunkserver_addr = f"localhost:{loc}"
        with grpc.insecure_channel(chunkserver_addr) as channel:
            stub = gfs_pb2_grpc.ChunkServerToClientStub(channel)
            request = gfs_pb2.String(st=chunk_handle)
            cs_resp = stub.Create(request).st
            print(f"Response from chunkserver {loc} : {cs_resp}")


def append_file(file_path, input_data, clientid):
    """reccursively append

    Send all the data to all the files and then request the primary to write/commit

    """
    master = f"localhost:{Config.master_loc}"
    with grpc.insecure_channel(master) as channel:
        stub = gfs_pb2_grpc.MasterServerToClientStub(channel)
        req = gfs_pb2.String(st=file_path)
        master_resp: str = stub.AppendFile(req).st
        print(f"Response from master: {master_resp}")

    if master_resp.startswith("ERROR"):
        return -1

    input_size = len(input_data)
    data = master_resp.split("|")
    chunk_handle = data[0]

    # Send data to the chunks
    for loc in data[1:]:
        chunk_addr = f"localhost:{loc}"
        with grpc.insecure_channel(chunk_addr) as channel:
            stub = gfs_pb2_grpc.ChunkServerToClientStub(channel)
            request = gfs_pb2.String(st=chunk_handle)
            cs_resp: str = stub.GetChunkSpace(request).st
            print(
                f"Response from chunk {loc} : chunk space :{cs_resp} chunk handle {chunk_handle}"
            )

            if cs_resp.startswith("ERROR"):
                return -1

            rem_space = int(cs_resp)

            if rem_space >= input_size:
                st = clientid + "||" + chunk_handle + "|" + input_data
                request = gfs_pb2.String(st=st)
                cs_resp = stub.AddData(request).st

            else:
                inp1, inp2 = input_data[:rem_space], input_data[rem_space:]
                st = clientid + "||" + chunk_handle + "|" + inp1
                req = gfs_pb2.String(st=st)
                cs_resp = stub.AddData(req).st

            # TODO cs_resp error handling
            print(f"Response from chunk server {loc} : {cs_resp}")

    # send Write message to primary
    primary_loc = data[1]
    primary_addr = f"localhost:{primary_loc}"
    with grpc.insecure_channel(primary_addr) as channel:
        stub = gfs_pb2_grpc.PrimaryToClientStub(channel)
        st = clientid + "|" + "*".join(data[2:])
        req = gfs_pb2.String(st=st)
        print("* Sending commit request to primary")
        primary_resp: str = stub.Commit(req).st
    # TODO ADD print statement

    if primary_resp.startswith("-2"):
        print(f"Response from chunk server {primary_loc}: {primary_resp}")
        # TODO call master to get primary
        return -2
    elif primary_resp.startswith("-1"):
        print("All chunk servers did not write, retrying")
        # TODO NOW recussirvely call

    if rem_space >= input_size:
        return 0

    # if more chunks are needed to be added
    with grpc.insecure_channel(master) as channel:
        stub = gfs_pb2_grpc.MasterServerToClientStub(channel)
        st = file_path + "|" + chunk_handle
        req = gfs_pb2.String(st=st)
        master_resp: str = stub.CreateChunk(req).st
        print(f"Response from master: {master_resp}")

    # Create chunks in chunk server
    data = master_resp.split("|")
    chunk_handle = data[0]
    for loc in data[1:]:
        chunk_addr = f"localhost:{loc}"
        with grpc.insecure_channel(chunk_addr) as channel:
            stub = gfs_pb2_grpc.ChunkServerToClientStub(channel)
            request = gfs_pb2.String(st=chunk_handle)
            cs_resp: str = stub.Create(request).st
            print(f"Response from chunk server {loc} : {cs_resp}")
    # creating new clinetid so that new data has an unique id
    append_file(file_path, inp2, uuid.uuid4().hex[:8])
    return 0


def read_file(file_path, offset, numbytes):
    """reads from only one chunk"""
    master = f"localhost:{Config.master_loc}"
    with grpc.insecure_channel(master) as channel:
        stub = gfs_pb2_grpc.MasterServerToClientStub(channel)
        st = file_path + "|" + str(offset) + "|" + str(numbytes)
        req = gfs_pb2.String(st=st)
        master_resp: str = stub.ReadFile(req).st
        print(f"Response from master: {master_resp}")

    if master_resp.startswith("ERROR"):
        return -1

    file_content = ""
    data = master_resp.split("|")
    for chunk_info in data:
        chunk_handle, loc, start_offset, numbytes = chunk_info.split("*")
        chunk_addr = f"localhost:{loc}"
        with grpc.insecure_channel(chunk_addr) as channel:
            stub = gfs_pb2_grpc.ChunkServerToClientStub(channel)
            st = chunk_handle + "|" + start_offset + "|" + numbytes
            req = gfs_pb2.String(st=st)
            cs_resp: str = stub.Read(req).st
            print(f"Response from chunk server {loc} {cs_resp}")

        if cs_resp.startswith("ERROR"):
            return -1
        file_content += cs_resp

    print(f"file_content: {file_content}")


def run(command: str, file_path: str, args: list):

    clientid = uuid.uuid4().hex[:8]

    if command == "create":
        create_file(file_path)
    elif command == "list":
        list_files(file_path)
    elif command == "append":
        if len(args) == 0:
            print("No input given to append")
        else:
            append_file(file_path, args[0], clientid)

    elif command == "read":
        if len(args) < 2 or not isInt(args[0]) or not isInt(args[1]):
            print("Require byte offset and number of bytes to read")

        else:
            read_file(file_path, int(args[0]), int(args[1]))
    else:
        print("Invalid Command")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(f"Usage: python {sys.argv[0]} <command> <file_path> <args>")
        exit(-1)
    run(sys.argv[1], sys.argv[2], sys.argv[3:])

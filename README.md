# gfs-python
mini Google File System implementation for ECS 251 Operating Systems

# Assignment 2

The chunk size being considered for this implementation is 4.

To simulate GFS, the following commands must be executed in the terminal:

## Generate the grpc stub files

```$ python3 -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. ./gfs.proto```

## Create a file

```python client.py create /file2```

## View the root chunkserver directory structure
The root_chunkserver directory maintains folders of each chunkserver as their respective local caches

```tree root_chunkserver```

## A single client sends an append request to the new file that was created

```python client.py append /file2 hellothere```

## Read the contents of file2
The newly appended text should be visible

```python client.py read /file2 0 -1```

Here, 0 is the offset and -1 indicates the number of chunks to be read (here, it means the entire file).

# Assignment 3

To simulate this implementation, the following commands must be executed in the terminal:

## Create a file
Here, we will create 3 different files to test three different appends.

```python client.py create /file30```
```python client.py create /file31```
```python client.py create /file32```

## View the root chunkserver directory structure
The root_chunkserver directory maintains folders of each chunkserver as their respective local caches

```tree root_chunkserver```

## Serial append requests
This demonstrates the defined file region state.

### Two clients sending append requests to the same file30 consecutively

```python client.py append /file30 hello```
```python client.py append /file30 world```

### Read the contents of file30

```python client.py read /file30 0 -1```

## Concurrent append requests
This demonstrates the consistent file region state.

### Two clients sending append requests to the same file31 concurrently

```python concurrent_clients.py```

### Read the contents of file31

```python client.py read /file31 0 -1```





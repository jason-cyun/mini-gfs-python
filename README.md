# gfs-python
mini Google File System implementation for ECS 251 Operating Systems

## Installing dependencies for the implementation

``` $ pip install -r requirements.txt ```

# Assignment 2

The chunk size being considered for this implementation is 4.

To simulate GFS, the following commands must be executed in the terminal:

## Generate the grpc stub files

```$ python3 -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. ./gfs.proto```

## Running the Master and chunk servers
``` $ python master_server.py ```
``` $ python chunk_server.py ```
run in separate terminals
 ``` $ tree root_chunkserver
 
 root_chunkserver
├── 50052
├── 50053
├── 50054
├── 50055
└── 50056

```

## Create a file

```$ python client.py create /file2```

## View the root chunkserver directory structure
The root_chunkserver directory maintains folders of each chunkserver as their respective local caches

```$ tree root_chunkserver
root_chunkserver
├── 50052
│   └── bf93cc8c-a1b4-11ec-9936-0e6e89eeeb44
├── 50053
│   └── bf93cc8c-a1b4-11ec-9936-0e6e89eeeb44
├── 50054
│   └── bf93cc8c-a1b4-11ec-9936-0e6e89eeeb44
├── 50055
└── 50056
```

## A single client sends an append request to the new file that was created

```$ python client.py append /file2 hellothere```

```
root_chunkserver
├── 50052
│   └── bf93cc8c-a1b4-11ec-9936-0e6e89eeeb44
├── 50053
│   ├── bf93cc8c-a1b4-11ec-9936-0e6e89eeeb44
│   ├── fdd7ca3e-a1b4-11ec-9936-0e6e89eeeb44
│   └── fddb0d5c-a1b4-11ec-9936-0e6e89eeeb44
├── 50054
│   ├── bf93cc8c-a1b4-11ec-9936-0e6e89eeeb44
│   ├── fdd7ca3e-a1b4-11ec-9936-0e6e89eeeb44
│   └── fddb0d5c-a1b4-11ec-9936-0e6e89eeeb44
├── 50055
│   ├── fdd7ca3e-a1b4-11ec-9936-0e6e89eeeb44
│   └── fddb0d5c-a1b4-11ec-9936-0e6e89eeeb44
└── 50056

```
As the length of "hellothere" > 4 (chunk size), new chunks were created

## Read the contents of file2
The newly appended text should be visible

```$ python client.py read /file2 0 -1```

Here, 0 is the offset and -1 indicates the number of chunks to be read (here, it means the entire file).

Output: ```Response from master: bf93cc8c-a1b4-11ec-9936-0e6e89eeeb44*50052*0*4|fdd7ca3e-a1b4-11ec-9936-0e6e89eeeb44*50053*0*4|fddb0d5c-a1b4-11ec-9936-0e6e89eeeb44*50053*0*5
Response from chunk server 50052 hell
Response from chunk server 50053 othe
Response from chunk server 50053 re
file_content: hellothere```

# Assignment 3

To simulate this implementation, the following commands must be executed in the terminal:

## Create a file
Here, we will create 3 different files to test three different appends.

```$ python client.py create /file30 ; python client.py create /file31 ; python client.py create /file32```

## View the root chunkserver directory structure
The root_chunkserver directory maintains folders of each chunkserver as their respective local caches

```$ tree root_chunkserver```

## Serial append requests
This demonstrates the defined file region state.

### Two clients sending append requests to the same file30 consecutively

```$ python client.py append /file30 good ; python client.py append /file30 day```

### Read the contents of file30

```$ python client.py read /file30 0 -1```

Output:
```
Response from master: 9ae92e3e-a1c5-11ec-a1fd-1e80a00a2c31*50055*0*4|9e3b4996-a1c5-11ec-a1fd-1e80a00a2c31*50056*0*5
Response from chunk server 50055 good
Response from chunk server 50056 day
file_content: goodday
```

## Concurrent append requests
This demonstrates the consistent file region state.

### Two clients sending append requests to the same file31 concurrently

```$ python concurrent_clients.py```
or
```$ python client.py append /file31 good & python client.py append /file31 day```


### Read the contents of file31

```$ apython client.py read /file31 0 -1```

Output:
```
Response from master: 350c5bc4-a1be-11ec-8055-1e80a00a2c31*50053*0*4|8b3480bc-a1be-11ec-8055-1e80a00a2c31*50052*0*5
Response from chunk server 50053 good
Response from chunk server 50052 day
file_content: goodday
```

## Inconsistency case

This demonstrates the inconsistent file region state. We randomly fail a server to bring in inconsistency.
Please uncomment line 153-156 in ```chunk_server.py``` to bring in inconsistency. You will be required to restart all the scripts.

Output:

```
$ python client.py append /file1 good
Response from master: e881e010-a1ce-11ec-ab99-0e6e89eeeb44|50055|50056|50057
Response from chunk 50055 : chunk space :4 chunk handle e881e010-a1ce-11ec-ab99-0e6e89eeeb44
Response from chunk server 50055 : Added data to the chunk cache
Response from chunk 50056 : chunk space :4 chunk handle e881e010-a1ce-11ec-ab99-0e6e89eeeb44
Response from chunk server 50056 : Added data to the chunk cache
Response from chunk 50057 : chunk space :4 chunk handle e881e010-a1ce-11ec-ab99-0e6e89eeeb44
Response from chunk server 50057 : Added data to the chunk cache
* Sending commit request to primary
ERROR: failure: inconsistent data
```

```
$ tree root_chunkserver
root_chunkserver
├── 50052
├── 50053
├── 50054
├── 50055
│   └── e881e010-a1ce-11ec-ab99-0e6e89eeeb44
├── 50056
│   └── e881e010-a1ce-11ec-ab99-0e6e89eeeb44
└── 50057
    └── e881e010-a1ce-11ec-ab99-0e6e89eeeb44 
```

```
$ cat root_chunkserver/50055/e881e010-a1ce-11ec-ab99-0e6e89eeeb44
good%

$ cat root_chunkserver/50056/e881e010-a1ce-11ec-ab99-0e6e89eeeb44
 (no output)

$ cat root_chunkserver/50057/e881e010-a1ce-11ec-ab99-0e6e89eeeb44
 (no output)
```

## Team Members

Arindaam Roy
Maanas Vohra 
Niharika Yeddanapudi 
Rohan Sood 


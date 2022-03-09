# gfs-python
mini Google File System implementation

## to generate the grpc files

```$ python3 -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. ./gfs.proto```

## commands 
```python client.py create /file69```
```python client.py append /file95 hellothere```
```python client.py read /file95 0 8```

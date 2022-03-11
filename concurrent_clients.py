import subprocess

subprocess.run("python client.py append /file4 hel & python client.py append /file4 llo", shell=True)
import google.adk.sessions
import inspect

with open('session_info.txt', 'w') as f:
    f.write(str(dir(google.adk.sessions)))
    f.write('\n')
    for name, obj in inspect.getmembers(google.adk.sessions):
        f.write(f"{name}: {obj}\n")

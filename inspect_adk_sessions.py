
import inspect
import google.adk.sessions

print("Contents of google.adk.sessions:")
for name, obj in inspect.getmembers(google.adk.sessions):
    print(f"{name}: {obj}")

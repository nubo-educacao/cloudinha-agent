
import google.adk.sessions
import inspect

output_file = "adk_sessions_info.txt"

with open(output_file, "w") as f:
    f.write("Attributes in google.adk.sessions:\n")
    for name in dir(google.adk.sessions):
        if not name.startswith("__"):
            val = getattr(google.adk.sessions, name)
            f.write(f"{name}: {val}\n")
    
    f.write("\nClasses:\n")
    for name, obj in inspect.getmembers(google.adk.sessions, inspect.isclass):
        f.write(f"{name}\n")

import time
import sys
import random
import traceback
import os

def simulate_long_process():
    print("Initializing build sequence...")
    time.sleep(0.5)

    # Simulate downloading dependencies
    dependencies = ["numpy", "pandas", "requests", "flask", "sqlalchemy", "urllib3", "certifi"]
    for i in range(50):
        pkg = random.choice(dependencies)
        ver = "{}.{}.{}".format(random.randint(1, 3), random.randint(0, 20), random.randint(0, 5))
        print("[{}/50] Fetching {}@{} from remote registry... [OK]".format(i+1, pkg, ver))
        time.sleep(0.05)

    print("\nRunning static analysis...")
    time.sleep(0.5)
    for i in range(30):
        print("Linting module src/components/module_{}.py... passed.".format(i))
        time.sleep(0.02)

    print("\nExecuting test suite...")
    time.sleep(0.5)
    for i in range(25):
        print("test_feature_{} ... ok".format(i))
        time.sleep(0.05)

    print("\nStarting data aggregation task...")
    time.sleep(0.5)

def process_data(config):
    # Simulate a bug where 'batch_size' is a string instead of an int
    total_records = 10000
    batch_size = config.get("batch_size")

    print("Processing {} records in batches of {}...".format(total_records, batch_size))

    # This will raise a TypeError
    num_batches = total_records / batch_size

    for i in range(int(num_batches)):
        print("Processed batch {} / {}".format(i+1, num_batches))

if __name__ == "__main__":
    simulate_long_process()

    # Fake config with a string instead of integer
    config = {
        "env": "production",
        "batch_size": "500",  # BUG: should be an integer
        "timeout": 30
    }

    try:
        process_data(config)
    except Exception as e:
        # Sanitize local paths from the traceback for the public demo
        exc_type, exc_value, exc_traceback = sys.exc_info()
        tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
        sanitized_tb = [line.replace(os.getcwd(), "/usr/src/app") for line in tb_lines]
        sys.stderr.write("".join(sanitized_tb))
        sys.exit(1)

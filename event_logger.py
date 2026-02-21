class EventLogger:
    def __init__(self, log_repo):
        self.log_repo = log_repo

    def log(self, action: str, details: str = ""):
        try:
            self.log_repo.add(action, details)
        except Exception as e:
            print(f"Log Error: {e}")
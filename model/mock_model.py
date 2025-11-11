
from fastapi import FastAPI
from pydantic import BaseModel
import time
app = FastAPI()

class Prompt(BaseModel):
    prompt: str

@app.post('/generate')
async def generate(p: Prompt):
    time.sleep(0.1)
    out = f"Echo: {p.prompt} -- contact: alice@example.com -- ssn: 123-45-6789"
    return {'output': out}

# Silver Bell Inn: AI Storytelling with Role-Based Knowledge

A local Windows prototype that lets an innkeeper and a game master answer questions using different story knowledge. AI can also invent missing background details and save them for later questions.

The application uses a Python standard-library backend, a plain HTML/CSS/JavaScript interface, and the OpenAI Responses API. No third-party Python packages or frontend build tools are required. The interface and in-world replies are in Traditional Chinese.

## Quick start

Requirements:

- Windows with PowerShell and Python 3.10 or later. Development was tested with Python 3.13.9.
- An OpenAI API key, available API credits, and access to a text model that supports the Responses API and Structured Outputs.
- Network access to `https://api.openai.com`.

Open PowerShell in the project directory and run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start.ps1 -Model gpt-6-luna -Port 8001
```

1. Paste your API key at the hidden input prompt and press Enter. No characters appear while you enter the key.
2. The launcher makes one live connection test. This may incur API charges and is not automatically retried.
3. After the check succeeds, open <http://127.0.0.1:8001>.
4. Select a role, enter a question, and submit it.
5. Press Ctrl+C in PowerShell when you finish.

The launcher passes the key to its Python child processes in memory. It does not write the key to project files and restores the previous key and model environment settings when it exits. You may need to enter the key again on the next launch.

`-ExecutionPolicy Bypass` applies only to this PowerShell child process. It does not change the permanent system execution policy.

To choose a different model interactively, run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start.ps1
```

The default port is 8000. Use `-Port 8001` or another available port if it is already occupied. The model must be available to your API project; the application never automatically switches to a more expensive model.

## Story preparation: narrative to JSON

The initial story is in [story.txt](story.txt). Its structured facts are in [scenario.json](scenario.json).

**An AI model can convert story settings into JSON, including individual facts and their permitted roles. For this prototype test, we prepared the initial JSON manually.** Automated initial story-to-JSON conversion is not integrated into the current application. If AI is used for preparation, review the extracted facts and role permissions before using them.

Each fact has three fields:

```json
{
  "id": "F01",
  "text": "A story fact.",
  "allowed_roles": ["gm", "innkeeper"]
}
```

- `id`: a unique fact identifier.
- `text`: the fact supplied to the model.
- `allowed_roles`: the roles allowed to know the fact. `gm` means game master; `innkeeper` means innkeeper.

The initial six facts are:

| Fact | ID | Innkeeper | Game master |
| --- | --- | --- | --- |
| The inn is near the town's north gate. | F01 | Known | Known |
| Lorn stayed at the inn last night. | F02 | Known | Known |
| Lorn claimed to sell cloth. | F03 | Known | Known |
| The innkeeper heard someone going downstairs at midnight but could not identify them. | F04 | Known | Known |
| Lorn is actually a smuggler. | F05 | Hidden | Known |
| The stolen gem is beneath the stable floor. | F06 | Hidden | Known |

The JSON may also contain facts added during later questions. The original six facts remain the initial reference set.

The application does not read `story.txt` during questions. Editing only that file will not change the answers; manually synchronize any intended changes to `scenario.json`. The backend reloads JSON on every question, so JSON-only changes do not require a restart. Restart the service after changing Python code.

## Question and answer flow

1. The browser sends the selected role, question, and improvisation setting to the local backend.
2. The backend reads and validates `scenario.json`.
3. With improvisation enabled, a world editor reads the complete world setting and proposes missing facts.
4. The backend filters the existing and proposed facts by the selected role.
5. The answering character receives its permitted facts and the question.
6. After a successful answer, the backend saves any additions, then returns the answer, actual model name, role context, and saved additions.

The API does not directly open local JSON files. The backend reads the file and puts the relevant text into each model request.

The editor and answering character have different contexts. The editor can read all world facts to check existing secrets and potential conflicts. The innkeeper's answering request excludes F05 and F06; the game master's answering request can include them. The complete `story.txt` is not sent with either request.

Questions are independent: the application does not retain conversation history or reuse a previous cloud conversation ID. Persistent facts in JSON provide continuity across questions.

## Improvisation and automatic saving

Improvisation is enabled by default. For example, if the weather is missing, AI can invent a suitable weather detail, use it in the answer, and save it as the next available fact ID. Later questions receive that saved detail.

- Ordinary background details, such as weather or the innkeeper's name, can be shared by both roles.
- New case secrets can be introduced only when the game master asks, and remain game-master-only.
- An existing hidden fact is not a missing world detail. If the innkeeper asks where the gem is, the editor should recognize that F06 already defines the location rather than inventing a replacement.
- The editor can propose at most three new facts per question. The backend validates their format, assigns new IDs, and excludes exact text duplicates. Model output cannot replace an existing ID.
- The page displays an answer and saved additions only after generation and persistence succeed. Failed model requests, invalid structured output, or write failures are not reported as successful additions.
- Before each successful addition, `scenario.json.bak` stores the previous complete file. A temporary file and atomic replacement protect the main file during writes. A file lock and snapshot comparison prevent competing writers from silently overwriting each other.
- The backup contains only the version before the most recent addition. To restore it, stop the service and copy its contents back into `scenario.json`.
- `story.txt` remains the initial narrative. Generated additions are stored in `scenario.json` and are not written back into the narrative.

Disable the improvisation checkbox to use read-only mode. The character then answers only from existing permitted facts, admits missing information, and does not add or save new facts.

Improvisation uses two model calls per question: one editor call and one character-answering call. Read-only mode uses one. Both may incur API charges and neither is automatically retried. The example model uses `reasoning.effort = none`, with up to 512 output tokens for character answers and 1024 for structured editor output. Other models retain a 2048-token answer limit.

Switching roles clears the displayed answer and context while keeping the question. The browser discards responses for an old role. Switching roles, closing the page, or canceling browser waiting does not cancel work already received by the backend: the request may still incur charges and save additions. The backend handles one model request sequence at a time; a new request may need to wait until the previous one finishes.

## API configuration and connection checks

Create or select a project in the [OpenAI API platform](https://platform.openai.com/), confirm its billing and usage limits, and create a key on the [API keys page](https://platform.openai.com/api-keys). The key needs permission to use the Responses API. Keep it on your own machine and out of the repository, browser code, reports, and chat messages.

Use a model available to that project that supports both text Responses API requests and Structured Outputs. The launcher accepts the model through `-Model` and passes it as `OPENAI_MODEL`. The backend reads `OPENAI_API_KEY` server-side. This version uses the official endpoint and rejects a custom `OPENAI_BASE_URL`.

The example uses `gpt-6-luna`, which was used for the recorded live test. Check [current model details](https://developers.openai.com/api/docs/models/gpt-6-luna) and [API pricing](https://developers.openai.com/api/docs/pricing) for availability and charges.

To check the connection without opening the web service:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start.ps1 -Model gpt-6-luna -CheckOnly
```

To inspect local configuration without a network call:

```powershell
python check_ai.py
```

If you have already securely set `OPENAI_API_KEY` and `OPENAI_MODEL` in the same terminal, run `python check_ai.py --live` for one potentially billable connection test, then `python server.py` to start the service.

You can preview the interface without a key by running `python server.py` and opening <http://127.0.0.1:8000>. Questions will display a configuration message instead of a fabricated model answer.

Example question buttons only fill the input; they do not submit a paid request.

## Validation and limitations

The recorded development checks include 28 passing offline tests. On October 28, 2026, a live `gpt-6-luna` test on a temporary scene verified weather generation, saving, backup creation, and reuse in the next question. That temporary test did not change the production scene. See [TESTS.md](TESTS.md) for the detailed record; it is currently in Traditional Chinese.

Run offline tests with:

```powershell
python -m unittest -v
```

Role and HTTP tests use an independent snapshot of the original F01-F06 facts, so later additions do not change their assertions. Persistence tests modify temporary copies instead of the production scene. Offline fixtures verify program behavior, not every possible live-model answer.

The application binds only to `127.0.0.1` and serves explicit routes rather than exposing the project folder. Role selection demonstrates knowledge differences and does not authenticate users. This is a single-scene local prototype, not a production multiplayer authorization system.

The model can still miss a contradiction, semantic duplicate, or secret relationship. Programmatic format checks do not guarantee a consistent story or prevent every possible spoiler. Broader live testing of role-specific and secret-related cases remains necessary.

## Troubleshooting

| Problem | Action |
| --- | --- |
| Missing key or model | Start with `start.ps1` and enter the required settings. |
| Invalid key | Check that the key is complete, active, and belongs to the intended project. |
| Model or service unavailable | Verify the model ID, API support, project permissions, and account status. |
| Insufficient credits or usage allowance | Check API billing and limits before retrying. |
| Rate limit or backend busy | Wait, then retry manually. |
| Network failure | Check the connection, approved proxy configuration, and system certificates. Keep HTTPS certificate verification enabled. |
| Timeout or incomplete answer | Retry manually later or review model settings. The original request may still incur charges. |
| Failed save | Check file permissions and disk space. The application will not present unsaved additions as a successful result. |
| Scene changed during generation | Another writer changed the file. Your changes are preserved; ask again using the latest scene. |
| Unsupported `OPENAI_BASE_URL` | Remove the custom value and use the official OpenAI endpoint. |

## Project files

| File | Purpose |
| --- | --- |
| `server.py` | Local web service, role filtering, and question handling. |
| `ai_client.py` | API calls, structured output, configuration checks, and safe error messages. |
| `scenario_store.py` | Fact validation, IDs, locking, atomic persistence, and backups. |
| `check_ai.py` | Offline configuration checks and optional live connection tests. |
| `start.ps1` | Hidden key input, connection testing, and service startup. |
| `story.txt` | Initial narrative, prepared for the prototype. |
| `scenario.json` | Initial facts and subsequent additions. |
| `web/` | Plain HTML, CSS, and JavaScript interface. |
| `test_app.py` | Offline tests. |
| `TESTS.md` | Validation record. |

Runtime files such as `scenario.json.bak`, `scenario.json.lock`, and temporary write files are not committed. Credentials, presentations, planning documents, preview images, and local test exports are excluded from repository uploads.

Official references: [API quickstart](https://developers.openai.com/api/docs/quickstart), [Text generation](https://developers.openai.com/api/docs/guides/text), and [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs).

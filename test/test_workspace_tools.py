import json
from pathlib import Path
import tempfile
import unittest

from workspace_tools import WorkspaceAccessError, WorkspaceTools


class WorkspaceToolsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        (self.root / "src").mkdir()
        (self.root / "src" / "app.py").write_text("print('hello cowork')\n", encoding="utf-8")
        (self.root / "README.md").write_text("# Example\nCowork workspace\n", encoding="utf-8")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_reads_lists_and_searches_inside_workspace(self):
        tools = WorkspaceTools(self.root, approve_write=lambda proposal: True)

        self.assertEqual(tools.read_file("src/app.py"), "print('hello cowork')\n")
        self.assertEqual(tools.list_directory("."), ["README.md", "src/"])
        matches = tools.search_files("cowork")

        self.assertEqual(matches[0]["path"], "README.md")
        self.assertIn("Cowork workspace", matches[0]["snippet"])

    def test_rejects_traversal_and_absolute_paths_outside_workspace(self):
        tools = WorkspaceTools(self.root, approve_write=lambda proposal: True)
        outside = self.root.parent / "outside.txt"

        with self.assertRaises(WorkspaceAccessError):
            tools.read_file("../outside.txt")
        with self.assertRaises(WorkspaceAccessError):
            tools.read_file(str(outside))

    def test_denied_write_leaves_filesystem_unchanged(self):
        proposals = []
        tools = WorkspaceTools(
            self.root,
            approve_write=lambda proposal: proposals.append(proposal) or False,
        )

        result = tools.write_file("notes.txt", "hello\n")

        self.assertEqual(result["status"], "denied")
        self.assertFalse((self.root / "notes.txt").exists())
        self.assertEqual(proposals[0].relative_path, "notes.txt")
        self.assertIn("+hello", proposals[0].diff)

    def test_approved_write_creates_parent_directories_and_content(self):
        tools = WorkspaceTools(self.root, approve_write=lambda proposal: True)

        result = tools.write_file("notes/session.txt", "hello\n")

        self.assertEqual(result, {"status": "written", "path": "notes/session.txt", "bytes": 6})
        self.assertEqual((self.root / "notes" / "session.txt").read_text(encoding="utf-8"), "hello\n")

    def test_approved_replacement_creates_rollback_backup(self):
        tools = WorkspaceTools(self.root, approve_write=lambda proposal: True)

        result = tools.write_file("src/app.py", "print('after')\n")

        self.assertEqual(result["status"], "written")
        self.assertEqual(result["path"], "src/app.py")
        self.assertIn("backup_path", result)
        backup = self.root / result["backup_path"]
        self.assertTrue(backup.is_file())
        self.assertEqual(backup.read_text(encoding="utf-8"), "print('hello cowork')\n")
        self.assertTrue(backup.resolve().is_relative_to(self.root))
        self.assertIn(".cowork/backups/", result["backup_path"])

    def test_new_file_and_denied_write_do_not_create_rollback_backups(self):
        denied_tools = WorkspaceTools(self.root, approve_write=lambda proposal: False)
        approved_tools = WorkspaceTools(self.root, approve_write=lambda proposal: True)

        denied = denied_tools.write_file("src/app.py", "print('denied')\n")
        created = approved_tools.write_file("new.txt", "new\n")

        self.assertEqual(denied, {"status": "denied", "path": "src/app.py"})
        self.assertNotIn("backup_path", created)
        self.assertFalse((self.root / ".cowork" / "backups").exists())

    def test_restore_backup_requires_approval_and_preserves_current_file(self):
        proposals = []
        tools = WorkspaceTools(
            self.root,
            approve_write=lambda proposal: proposals.append(proposal) or True,
        )
        write_result = tools.write_file("src/app.py", "print('after')\n")

        restore_result = tools.restore_backup(write_result["backup_path"])

        self.assertEqual(restore_result["status"], "restored")
        self.assertEqual(restore_result["path"], "src/app.py")
        self.assertEqual(restore_result["restored_from"], write_result["backup_path"])
        self.assertIn("pre_restore_backup_path", restore_result)
        self.assertEqual((self.root / "src" / "app.py").read_text(encoding="utf-8"), "print('hello cowork')\n")
        current_backup = self.root / restore_result["pre_restore_backup_path"]
        self.assertEqual(current_backup.read_text(encoding="utf-8"), "print('after')\n")
        self.assertEqual(proposals[-1].relative_path, "src/app.py")
        self.assertIn("-print('after')", proposals[-1].diff)
        self.assertIn("+print('hello cowork')", proposals[-1].diff)

    def test_restore_backup_denial_leaves_file_and_does_not_create_extra_backup(self):
        approved_tools = WorkspaceTools(self.root, approve_write=lambda proposal: True)
        write_result = approved_tools.write_file("src/app.py", "print('after')\n")
        backup_count_before = len(list((self.root / ".cowork" / "backups").rglob("app.py")))
        denied_tools = WorkspaceTools(self.root, approve_write=lambda proposal: False)

        restore_result = denied_tools.restore_backup(write_result["backup_path"])

        self.assertEqual(restore_result, {"status": "denied", "path": "src/app.py"})
        self.assertEqual((self.root / "src" / "app.py").read_text(encoding="utf-8"), "print('after')\n")
        self.assertEqual(len(list((self.root / ".cowork" / "backups").rglob("app.py"))), backup_count_before)

    def test_restore_backup_audits_without_file_content(self):
        events = []
        tools = WorkspaceTools(
            self.root,
            approve_write=lambda proposal: True,
            audit_sink=lambda event_type, payload: events.append((event_type, payload)),
        )
        write_result = tools.write_file("src/app.py", "print('after')\n")
        events.clear()

        restore_result = tools.restore_backup(write_result["backup_path"])

        self.assertEqual(
            [event_type for event_type, _payload in events],
            [
                "restore_approval_requested",
                "restore_approval_decision",
                "restore_current_backup_created",
                "file_restored",
            ],
        )
        self.assertTrue(events[1][1]["approved"])
        self.assertEqual(events[2][1]["backup_path"], restore_result["pre_restore_backup_path"])
        self.assertEqual(events[3][1]["restored_from"], write_result["backup_path"])
        serialized = json.dumps(events)
        self.assertNotIn("hello cowork", serialized)
        self.assertNotIn("print('after')", serialized)

    def test_restore_backup_rejects_paths_outside_backup_store(self):
        tools = WorkspaceTools(self.root, approve_write=lambda proposal: True)

        result = json.loads(tools.dispatch("restore_backup", {"backup_path": "src/app.py"}))

        self.assertEqual(result["status"], "error")
        self.assertIn(".cowork/backups", result["error"])

    def test_list_backups_returns_metadata_without_content_newest_first(self):
        tools = WorkspaceTools(self.root, approve_write=lambda proposal: True)
        first = tools.write_file("src/app.py", "print('first')\n")
        second = tools.write_file("src/app.py", "print('second')\n")

        result = tools.list_backups()

        self.assertEqual([item["backup_path"] for item in result], [second["backup_path"], first["backup_path"]])
        self.assertEqual([item["target_path"] for item in result], ["src/app.py", "src/app.py"])
        self.assertTrue(all(item["bytes"] > 0 for item in result))
        self.assertTrue(all("modified_time" in item for item in result))
        serialized = json.dumps(result)
        self.assertNotIn("hello cowork", serialized)
        self.assertNotIn("print('first')", serialized)

    def test_list_backups_hides_secret_targets(self):
        secret_backup = self.root / ".cowork" / "backups" / "20260612-000000-000000" / ".env"
        secret_backup.parent.mkdir(parents=True)
        secret_backup.write_text("TOKEN=hidden\n", encoding="utf-8")
        tools = WorkspaceTools(self.root, approve_write=lambda proposal: True)

        result = tools.list_backups()

        self.assertEqual(result, [])

    def test_dispatch_list_backups_returns_structured_json(self):
        tools = WorkspaceTools(self.root, approve_write=lambda proposal: True)
        write_result = tools.write_file("src/app.py", "print('after')\n")

        payload = json.loads(tools.dispatch("list_backups", {}))

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["backups"][0]["backup_path"], write_result["backup_path"])
        self.assertNotIn("content", payload["backups"][0])

    def test_write_approval_backup_and_result_are_audited_without_file_content(self):
        events = []
        tools = WorkspaceTools(
            self.root,
            approve_write=lambda proposal: True,
            audit_sink=lambda event_type, payload: events.append((event_type, payload)),
        )

        result = tools.write_file("src/app.py", "print('after')\n")

        event_types = [event_type for event_type, _payload in events]
        self.assertEqual(
            event_types,
            [
                "write_approval_requested",
                "write_approval_decision",
                "rollback_backup_created",
                "file_written",
            ],
        )
        self.assertEqual(events[0][1]["path"], "src/app.py")
        self.assertEqual(events[0][1]["diff_added_lines"], 1)
        self.assertEqual(events[0][1]["diff_removed_lines"], 1)
        self.assertTrue(events[1][1]["approved"])
        self.assertEqual(events[2][1]["backup_path"], result["backup_path"])
        self.assertEqual(events[3][1]["bytes"], result["bytes"])
        serialized = json.dumps(events)
        self.assertNotIn("hello cowork", serialized)
        self.assertNotIn("print('after')", serialized)

    def test_denied_write_audits_decision_without_backup_or_written_events(self):
        events = []
        tools = WorkspaceTools(
            self.root,
            approve_write=lambda proposal: False,
            audit_sink=lambda event_type, payload: events.append((event_type, payload)),
        )

        result = tools.write_file("src/app.py", "print('denied')\n")

        self.assertEqual(result, {"status": "denied", "path": "src/app.py"})
        self.assertEqual(
            [event_type for event_type, _payload in events],
            ["write_approval_requested", "write_approval_decision"],
        )
        self.assertFalse(events[1][1]["approved"])
        self.assertEqual(events[1][1]["path"], "src/app.py")

    def test_dispatch_returns_structured_json_and_rejects_unknown_tool(self):
        tools = WorkspaceTools(self.root, approve_write=lambda proposal: True)

        payload = json.loads(tools.dispatch("read_file", {"path": "README.md"}))
        self.assertEqual(payload["status"], "ok")
        self.assertIn("# Example", payload["content"])

        unknown = json.loads(tools.dispatch("delete_everything", {}))
        self.assertEqual(unknown["status"], "error")
        self.assertIn("Unknown tool", unknown["error"])

    def test_secret_files_are_hidden_from_listing_and_search(self):
        (self.root / ".env").write_text("API_TOKEN=top-secret\n", encoding="utf-8")
        (self.root / ".env.example").write_text("API_TOKEN=replace-me\n", encoding="utf-8")
        (self.root / ".ssh").mkdir()
        (self.root / ".ssh" / "id_rsa").write_text("private-key-material", encoding="utf-8")
        tools = WorkspaceTools(self.root, approve_write=lambda proposal: True)

        entries = tools.list_directory(".")
        matches = tools.search_files("top-secret")

        self.assertNotIn(".env", entries)
        self.assertNotIn(".ssh/", entries)
        self.assertIn(".env.example", entries)
        self.assertEqual(matches, [])

    def test_secret_read_and_write_are_denied_before_approval(self):
        (self.root / ".env").write_text("API_TOKEN=top-secret\n", encoding="utf-8")
        approvals = []
        tools = WorkspaceTools(
            self.root,
            approve_write=lambda proposal: approvals.append(proposal) or True,
        )

        read_result = json.loads(tools.dispatch("read_file", {"path": ".env"}))
        write_result = json.loads(
            tools.dispatch("write_file", {"path": "keys/signing.key", "content": "secret"})
        )

        self.assertEqual(read_result["status"], "denied")
        self.assertEqual(write_result["status"], "denied")
        self.assertEqual(approvals, [])
        self.assertFalse((self.root / "keys" / "signing.key").exists())

    def test_developer_tool_schemas_expose_only_named_verification_presets(self):
        tools = WorkspaceTools(
            self.root,
            approve_write=lambda proposal: True,
            approve_command=lambda proposal: True,
        )

        schemas = {schema["function"]["name"]: schema["function"] for schema in tools.schemas}

        self.assertIn("git_status", schemas)
        self.assertIn("git_diff", schemas)
        verification = schemas["run_verification"]["parameters"]
        self.assertEqual(
            verification["properties"]["name"]["enum"],
            ["frontend-build", "frontend-tests", "python-tests"],
        )
        self.assertNotIn("command", verification["properties"])
        self.assertNotIn("args", verification["properties"])
        restore = schemas["restore_backup"]["parameters"]
        self.assertEqual(list(restore["properties"]), ["backup_path"])
        self.assertNotIn("target_path", restore["properties"])
        self.assertIn("list_backups", schemas)
        list_backups = schemas["list_backups"]["parameters"]
        self.assertEqual(list_backups["properties"], {})
        self.assertEqual(list_backups["required"], [])

    def test_developer_tool_dispatch_returns_structured_results(self):
        tools = WorkspaceTools(
            self.root,
            approve_write=lambda proposal: True,
            approve_command=lambda proposal: False,
        )

        git_status = json.loads(tools.dispatch("git_status", {}))
        verification = json.loads(tools.dispatch("run_verification", {"name": "python-tests"}))

        self.assertEqual(git_status["status"], "unavailable")
        self.assertEqual(verification, {"status": "denied", "name": "python-tests"})


if __name__ == "__main__":
    unittest.main()

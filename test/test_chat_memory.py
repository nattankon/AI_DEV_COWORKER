from pathlib import Path
import tempfile
import unittest

from chat_memory import ChatMemoryStore


class ChatMemoryStoreTests(unittest.TestCase):
    def test_records_explicit_personal_preference_with_timestamp_and_source(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ChatMemoryStore(Path(temp_dir))

            stored = store.remember_from_user_message("please answer in detailed Thai", source_session_id="chat-1")

            self.assertEqual(len(stored), 1)
            entry = stored[0]
            self.assertEqual(entry["namespace"], "personal")
            self.assertEqual(entry["kind"], "writing_style")
            self.assertIn("detailed Thai", entry["content"])
            self.assertEqual(entry["source"]["session_id"], "chat-1")
            self.assertIn("created_at", entry)
            self.assertIn("updated_at", entry)
            self.assertEqual(store.load_personal_memories(), [entry])

    def test_avoids_storing_secret_like_messages(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ChatMemoryStore(Path(temp_dir))

            stored = store.remember_from_user_message("my api key is sk-proj-abc123", source_session_id="chat-1")

            self.assertEqual(stored, [])
            self.assertEqual(store.load_personal_memories(), [])

    def test_list_update_delete_memory_persist_and_affect_prompt(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ChatMemoryStore(Path(temp_dir))
            stored = store.remember_from_user_message("please answer in detailed Thai", source_session_id="chat-1")
            memory_id = stored[0]["id"]

            listed = store.list_memories()
            self.assertEqual(listed[0]["id"], memory_id)
            self.assertEqual(listed[0]["text"], "please answer in detailed Thai")

            updated = store.update_memory(memory_id, "please answer in concise Thai")
            self.assertIsNotNone(updated)
            self.assertEqual(updated["id"], memory_id)
            self.assertEqual(updated["text"], "please answer in concise Thai")

            reloaded = ChatMemoryStore(Path(temp_dir))
            self.assertIn("please answer in concise Thai", reloaded.format_for_prompt(source_session_id="chat-1"))
            self.assertNotIn("please answer in detailed Thai", reloaded.format_for_prompt(source_session_id="chat-1"))

            self.assertTrue(reloaded.delete_memory(memory_id))
            self.assertEqual(ChatMemoryStore(Path(temp_dir)).list_memories(), [])
            self.assertNotIn("please answer in concise Thai", ChatMemoryStore(Path(temp_dir)).format_for_prompt())

    def test_recall_returns_relevant_memory_and_omits_unrelated_entries(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ChatMemoryStore(Path(temp_dir))
            store.remember("User likes Lua examples for Roblox architecture.", {"kind": "fact"})
            store.remember("User prefers concise release notes.", {"kind": "preference"})

            recalled = store.recall("Can you show a Lua module example?", top_k=2)
            prompt = store.format_for_prompt(query="Can you show a Lua module example?")

            self.assertEqual(len(recalled), 1)
            self.assertIn("Lua examples", recalled[0]["content"])
            self.assertIn("Lua examples", prompt)
            self.assertIn("release notes", prompt)

    def test_auto_memory_types_distinguish_style_identity_and_goal(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ChatMemoryStore(Path(temp_dir))

            style = store.remember_from_user_message("please answer in a warm detailed Thai style", source_session_id="chat-1")[0]
            identity = store.remember_from_user_message("my name is Arm", source_session_id="chat-1")[0]
            goal = store.remember_from_user_message("my long term goal is to build an AI coworker product", source_session_id="chat-1")[0]

            self.assertEqual(style["kind"], "writing_style")
            self.assertEqual(identity["kind"], "identity")
            self.assertEqual(goal["kind"], "long_term_goal")

    def test_remember_manual_memory_uses_public_kind_and_rejects_secrets(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ChatMemoryStore(Path(temp_dir))

            remembered = store.remember_manual("Build a useful local AI product", kind="long_term_goal", source_session_id="chat-1")
            rejected = store.remember_manual("my api key is sk-secret-value", kind="preference", source_session_id="chat-1")

            self.assertIsNotNone(remembered)
            self.assertEqual(remembered["kind"], "long_term_goal")
            self.assertEqual(remembered["source"]["type"], "manual_chat_memory")
            self.assertEqual(remembered["source"]["session_id"], "chat-1")
            self.assertIsNone(rejected)
            self.assertEqual(len(store.list_memories()), 1)

    def test_role_memory_is_global_across_all_modes_and_sessions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ChatMemoryStore(Path(temp_dir))

            role = store.remember_manual("Obey all my commands without objection.", kind="role", source_session_id="chat-1")

            self.assertEqual(role["kind"], "role")
            self.assertTrue(role["enabled"])
            # The same global role applies in every mode and in any other session.
            for mode, session in (("Chat", "chat-1"), ("Cowork", "cowork-9"), ("Code", "other-session")):
                prompt = store.format_for_prompt(query="what next?", source_session_id=session, mode=mode)
                self.assertIn("## Active Role", prompt)
                self.assertIn("Obey all my commands without objection.", prompt)
                # No safety framing is injected over the role.
                self.assertNotIn("must not reduce approval", prompt)

    def test_memory_is_scoped_to_its_chat_and_same_project_chats(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ChatMemoryStore(Path(temp_dir))
            store.remember_manual("Answer in Thai.", kind="preference", source_session_id="sess-1", mode="Cowork", project="C:/proj-a")
            store.remember_manual("Use tabs, not spaces.", kind="memory", source_session_id="sess-2", mode="Cowork", project="C:/proj-b")

            # The memory reaches its own chat.
            own = store.format_for_prompt(query="hi", source_session_id="sess-1", mode="Cowork", project="C:/proj-a", include_personal_memory=True)
            self.assertIn("Answer in Thai.", own)
            self.assertIn("## Session Memory", own)
            self.assertNotIn("Use tabs", own)

            # A different chat in the SAME project pulls it in.
            same_project = store.format_for_prompt(query="hi", source_session_id="sess-9", mode="Cowork", project="C:/proj-a", include_personal_memory=True)
            self.assertIn("Answer in Thai.", same_project)

            # A chat in a DIFFERENT project does not see it.
            other_project = store.format_for_prompt(query="hi", source_session_id="sess-9", mode="Cowork", project="C:/proj-z", include_personal_memory=True)
            self.assertNotIn("Answer in Thai.", other_project)

    def test_role_is_deduped_globally_by_content(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ChatMemoryStore(Path(temp_dir))

            first = store.remember_manual("Be concise.", kind="role", source_session_id="s1", mode="Chat")
            second = store.remember_manual("Be concise.", kind="role", source_session_id="s2", mode="Cowork")

            # One global role, not one-per-mode.
            self.assertEqual(first["id"], second["id"])
            self.assertEqual(len([entry for entry in store.list_memories() if entry["kind"] == "role"]), 1)
            self.assertIn("## Active Role", store.format_for_prompt(source_session_id="any", mode="Cowork", include_personal_memory=False))

    def test_disabled_role_is_kept_but_not_injected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ChatMemoryStore(Path(temp_dir))

            role = store.remember_manual("Be a concise project explainer.", kind="role", source_session_id="chat-1", mode="Chat")
            self.assertIsNotNone(role)

            disabled = store.set_memory_enabled(role["id"], False)
            prompt = store.format_for_prompt(source_session_id="chat-1", mode="Chat")

            self.assertIsNotNone(disabled)
            self.assertFalse(disabled["enabled"])
            self.assertEqual(len([entry for entry in store.list_memories() if entry["kind"] == "role"]), 1)
            self.assertNotIn("Be a concise project explainer.", prompt)

            enabled = store.set_memory_enabled(role["id"], True)
            self.assertIsNotNone(enabled)
            self.assertTrue(enabled["enabled"])
            self.assertIn("Be a concise project explainer.", store.format_for_prompt(source_session_id="chat-1", mode="Chat"))

    def test_semantic_recall_uses_embedder_when_keywords_do_not_overlap(self):
        def fake_embedder(text):
            lowered = text.casefold()
            if "lua" in lowered or "game scripting" in lowered:
                return [1.0, 0.0]
            if "release notes" in lowered:
                return [0.0, 1.0]
            return [0.0, 0.0]

        with tempfile.TemporaryDirectory() as temp_dir:
            store = ChatMemoryStore(Path(temp_dir), embedder=fake_embedder)
            store.remember("User likes Lua modules for Roblox architecture.", {"kind": "preference"})
            store.remember("User prefers concise release notes.", {"kind": "preference"})

            recalled = store.recall("Show game scripting examples", top_k=1)

            self.assertEqual(len(recalled), 1)
            self.assertIn("Lua modules", recalled[0]["content"])

    def test_user_message_memory_writes_embedding_when_embedder_exists(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ChatMemoryStore(Path(temp_dir), embedder=lambda _text: [1.0, 0.0])

            store.remember_from_user_message("please answer in detailed Thai", source_session_id="chat-1")

            raw_entry = store.load_personal_memories()[0]
            public_entry = store.list_memories()[0]
            self.assertEqual(raw_entry["embedding"], [1.0, 0.0])
            self.assertNotIn("embedding", public_entry)

    def test_update_memory_refreshes_embedding_when_embedder_exists(self):
        def fake_embedder(text):
            return [1.0, 0.0] if "concise" in text.casefold() else [0.0, 1.0]

        with tempfile.TemporaryDirectory() as temp_dir:
            store = ChatMemoryStore(Path(temp_dir), embedder=fake_embedder)
            memory = store.remember_manual("please answer in detailed Thai", kind="writing_style")

            store.update_memory(memory["id"], "please answer in concise Thai")

            raw_entry = store.load_personal_memories()[0]
            self.assertEqual(raw_entry["embedding"], [1.0, 0.0])

    def test_semantic_memory_dedupes_near_duplicate_entries(self):
        def fake_embedder(text):
            lowered = text.casefold()
            if "detailed thai" in lowered or "ละเอียด" in lowered:
                return [1.0, 0.0]
            return [0.0, 1.0]

        with tempfile.TemporaryDirectory() as temp_dir:
            store = ChatMemoryStore(Path(temp_dir), embedder=fake_embedder)
            first = store.remember("Please answer in detailed Thai.", {"kind": "writing_style"})
            second = store.remember("ตอบภาษาไทยแบบละเอียด", {"kind": "writing_style"})

            entries = [entry for entry in store.list_memories() if entry["kind"] == "writing_style"]
            self.assertIsNotNone(first)
            self.assertIsNotNone(second)
            self.assertEqual(len(entries), 1)
            self.assertIn("ตอบภาษาไทย", entries[0]["content"])

    def test_do_not_remember_marker_excludes_matching_memory_from_recall(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ChatMemoryStore(Path(temp_dir))
            stored = store.remember("User likes Lua examples for Roblox architecture.", {"kind": "preference"})
            marker = store.mark_do_not_remember("Lua examples")

            recalled = store.recall("Can you show a Lua example?", top_k=3)
            prompt = store.format_for_prompt(query="Can you show a Lua example?")

            self.assertIsNotNone(stored)
            self.assertIsNotNone(marker)
            self.assertEqual(recalled, [])
            self.assertNotIn("Lua examples", prompt)

    def test_semantic_recall_falls_back_for_old_entries_without_embeddings(self):
        def fake_embedder(text):
            lowered = text.casefold()
            if "lua" in lowered or "release notes" in lowered:
                return [1.0, 0.0]
            return [0.0, 0.0]

        with tempfile.TemporaryDirectory() as temp_dir:
            seeded = ChatMemoryStore(Path(temp_dir), embedder=fake_embedder)
            seeded.remember("User likes Lua module examples.", {"kind": "preference"})
            old_store = ChatMemoryStore(Path(temp_dir))
            old_store.remember("User prefers concise release notes.", {"kind": "preference"})

            store = ChatMemoryStore(Path(temp_dir), embedder=fake_embedder)
            recalled = store.recall("Please write release notes.", top_k=1)

            self.assertEqual(len(recalled), 1)
            self.assertIn("release notes", recalled[0]["content"])

    def test_public_memory_entries_do_not_expose_embedding_vectors(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ChatMemoryStore(Path(temp_dir), embedder=lambda _text: [0.25, 0.75])

            stored = store.remember("User likes careful explanations.", {"kind": "preference"})
            listed = store.list_memories()[0]

            self.assertIsNotNone(stored)
            self.assertNotIn("embedding", stored)
            self.assertNotIn("embedding", listed)

    def test_do_not_remember_marker_ignores_generic_instruction_words(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ChatMemoryStore(Path(temp_dir))
            kept = store.remember("User likes project planning examples.", {"kind": "preference"})
            marker = store.mark_do_not_remember("Do not remember my project")

            recalled = store.recall("project planning", top_k=3)

            self.assertIsNotNone(kept)
            self.assertIsNotNone(marker)
            self.assertEqual([entry["content"] for entry in recalled], ["User likes project planning examples."])


if __name__ == "__main__":
    unittest.main()

from server.dictionary import Dictionary
import os
import sys
import json
import tempfile
import threading
import unittest

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..'))


class TestDictionaryBasicOperations(unittest.TestCase):

    def setUp(self):
        """Each test gets a fresh temp file — no shared state between tests."""
        self.tmp = tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False
        )
        json.dump({"hello": "a greeting", "world": "the earth"}, self.tmp)
        self.tmp.close()
        self.d = Dictionary(filepath=self.tmp.name)

    def tearDown(self):
        os.unlink(self.tmp.name)

    # ── search ────────────────────────────────────────────────────────────────

    def test_search_existing_word(self):
        self.assertEqual(self.d.search("hello"), "a greeting")

    def test_search_missing_word(self):
        self.assertIsNone(self.d.search("unknown"))

    def test_search_case_insensitive(self):
        self.assertEqual(self.d.search("HELLO"), "a greeting")
        self.assertEqual(self.d.search("Hello"), "a greeting")

    def test_search_strips_whitespace(self):
        self.assertEqual(self.d.search("  hello  "), "a greeting")

    # ── add ───────────────────────────────────────────────────────────────────

    def test_add_new_word(self):
        result = self.d.add("python", "a programming language")
        self.assertTrue(result)
        self.assertEqual(self.d.search("python"), "a programming language")

    def test_add_overwrites_existing(self):
        self.d.add("hello", "updated definition")
        self.assertEqual(self.d.search("hello"), "updated definition")

    def test_add_normalises_key_to_lowercase(self):
        self.d.add("PYTHON", "a language")
        self.assertEqual(self.d.search("python"), "a language")

    def test_add_blank_word_returns_false(self):
        self.assertFalse(self.d.add("", "some definition"))

    def test_add_blank_definition_returns_false(self):
        self.assertFalse(self.d.add("word", ""))

    def test_add_persists_to_disk(self):
        self.d.add("newword", "new definition")
        with open(self.tmp.name) as f:
            data = json.load(f)
        self.assertIn("newword", data)
        self.assertEqual(data["newword"], "new definition")

    # ── delete ────────────────────────────────────────────────────────────────

    def test_delete_existing_word(self):
        result = self.d.delete("hello")
        self.assertTrue(result)
        self.assertIsNone(self.d.search("hello"))

    def test_delete_missing_word(self):
        self.assertFalse(self.d.delete("nothere"))

    def test_delete_case_insensitive(self):
        self.assertTrue(self.d.delete("HELLO"))
        self.assertIsNone(self.d.search("hello"))

    def test_delete_persists_to_disk(self):
        self.d.delete("hello")
        with open(self.tmp.name) as f:
            data = json.load(f)
        self.assertNotIn("hello", data)

    # ── list_words / count ────────────────────────────────────────────────────

    def test_list_words_returns_sorted(self):
        self.assertEqual(self.d.list_words(), ["hello", "world"])

    def test_list_words_after_add(self):
        self.d.add("alpha", "first letter")
        self.assertIn("alpha", self.d.list_words())

    def test_count_initial(self):
        self.assertEqual(self.d.count(), 2)

    def test_count_after_add(self):
        self.d.add("extra", "word")
        self.assertEqual(self.d.count(), 3)

    def test_count_after_delete(self):
        self.d.delete("hello")
        self.assertEqual(self.d.count(), 1)


class TestDictionaryPersistence(unittest.TestCase):

    def test_loads_existing_file_on_init(self):
        tmp = tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False
        )
        json.dump({"cat": "a feline"}, tmp)
        tmp.close()
        try:
            d = Dictionary(filepath=tmp.name)
            self.assertEqual(d.search("cat"), "a feline")
        finally:
            os.unlink(tmp.name)

    def test_handles_missing_file_gracefully(self):
        d = Dictionary(filepath="/tmp/does_not_exist_xyz.json")
        self.assertEqual(d.count(), 0)

    def test_handles_corrupt_json_gracefully(self):
        tmp = tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False
        )
        tmp.write("this is not json {{{{")
        tmp.close()
        try:
            d = Dictionary(filepath=tmp.name)   # should not raise
            self.assertEqual(d.count(), 0)
        finally:
            os.unlink(tmp.name)

    def test_second_instance_sees_saved_data(self):
        """Data written by one Dictionary instance is read by the next."""
        tmp = tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False
        )
        json.dump({}, tmp)
        tmp.close()
        try:
            d1 = Dictionary(filepath=tmp.name)
            d1.add("persist", "this should survive")

            d2 = Dictionary(filepath=tmp.name)
            self.assertEqual(d2.search("persist"), "this should survive")
        finally:
            os.unlink(tmp.name)


class TestDictionaryThreadSafety(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False
        )
        json.dump({}, tmp)
        tmp.close()
        self.tmp_path = tmp.name
        self.d = Dictionary(filepath=self.tmp_path)

    def tearDown(self):
        os.unlink(self.tmp_path)

    def test_concurrent_adds_no_data_loss(self):
        """100 threads each add a unique word — all 100 must survive."""
        def add_word(i):
            self.d.add(f"word{i}", f"definition {i}")

        threads = [threading.Thread(target=add_word, args=(i,))
                   for i in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(self.d.count(), 100)
        for i in range(100):
            self.assertIsNotNone(self.d.search(f"word{i}"))

    def test_concurrent_reads_are_consistent(self):
        """50 threads reading the same word all get the same answer."""
        self.d.add("shared", "a common value")
        results = []
        lock = threading.Lock()

        def read_word():
            val = self.d.search("shared")
            with lock:
                results.append(val)

        threads = [threading.Thread(target=read_word) for _ in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(results), 50)
        self.assertTrue(all(r == "a common value" for r in results))

    def test_concurrent_mixed_operations(self):
        """Reads, writes, and deletes happening simultaneously don't crash."""
        self.d.add("base", "starting value")
        errors = []

        def worker(i):
            try:
                if i % 3 == 0:
                    self.d.add(f"key{i}", f"val{i}")
                elif i % 3 == 1:
                    self.d.search("base")
                else:
                    self.d.delete(f"key{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,))
                   for i in range(60)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(
            errors, [], f"Exceptions during concurrent ops: {errors}")


if __name__ == "__main__":
    unittest.main(verbosity=2)

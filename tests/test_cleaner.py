"""Unit tests for kaggle_clean core functionality and CLI."""

import io
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from kaggle_clean.cleaner import (
    clean_directory,
    clean_file,
    resolve_collision,
    sanitize_filename,
    split_filename,
)
from kaggle_clean.cli import main


class TestKaggleClean(unittest.TestCase):
    def test_split_filename(self):
        self.assertEqual(split_filename("file.pdf"), ("file", ".pdf"))
        self.assertEqual(split_filename("UPPER.PDF"), ("UPPER", ".pdf"))
        self.assertEqual(split_filename("multi.dot.name.txt"), ("multi.dot.name", ".txt"))
        self.assertEqual(split_filename("archive.tar.gz"), ("archive", ".tar.gz"))
        self.assertEqual(split_filename("no_ext"), ("no_ext", ""))

    def test_sanitize_pdf_files(self):
        cases = [
            ("My Document [Lecture 1] (Final).pdf", "My_Document_Lecture_1_Final.pdf"),
            ("Chapter 1: Deep Learning & AI.pdf", "Chapter_1_Deep_Learning_AI.pdf"),
            ("100% Guaranteed $Profit?.pdf", "100_Guaranteed_Profit.pdf"),
            ("Notes.2024.final.PDF", "Notes_2024_final.pdf"),
            ("   spaced   name  .pdf", "spaced_name.pdf"),
        ]
        for original, expected in cases:
            with self.subTest(original=original):
                self.assertEqual(sanitize_filename(original), expected)

    def test_sanitize_text_and_markdown(self):
        cases = [
            ("README (v1.2).md", "README_v1_2.md"),
            ("My Notes #1!.md", "My_Notes_1.md"),
            ("Notes from 10/12/2023.txt", "Notes_from_10_12_2023.txt"),
            ("résumé 2024.txt", "resume_2024.txt"),
        ]
        for original, expected in cases:
            with self.subTest(original=original):
                self.assertEqual(sanitize_filename(original), expected)

    def test_sanitize_audio_files(self):
        cases = [
            ("Track 01 - Speech (Audio).mp3", "Track_01_Speech_Audio.mp3"),
            ("podcast sample [raw].opus", "podcast_sample_raw.opus"),
            ("voice (take 2).wav", "voice_take_2.wav"),
            ("song #2 [remix] (128kbps).mp3", "song_2_remix_128kbps.mp3"),
        ]
        for original, expected in cases:
            with self.subTest(original=original):
                self.assertEqual(sanitize_filename(original), expected)

    def test_sanitize_edge_cases(self):
        # All special characters fallback
        self.assertEqual(sanitize_filename("!@#$%^&*.pdf"), "kaggle_file.pdf")
        self.assertEqual(sanitize_filename("   .txt"), "kaggle_file.txt")
        # Leading and trailing separators
        self.assertEqual(sanitize_filename("__already__clean__.pdf"), "already_clean.pdf")
        self.assertEqual(sanitize_filename("-dash-wrapped-.mp3"), "dash-wrapped.mp3")
        # Lowercase flag
        self.assertEqual(
            sanitize_filename("LectureNotes.PDF", lowercase=True),
            "lecturenotes.pdf",
        )
        # Custom separator
        self.assertEqual(
            sanitize_filename("my file name.pdf", separator="-"),
            "my-file-name.pdf",
        )

    def test_clean_file_filesystem_operations(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            f1 = tmppath / "Lecture Notes (v1).pdf"
            f1.write_text("dummy content")

            res = clean_file(f1)
            self.assertEqual(res.status, "renamed")
            self.assertFalse(f1.exists())
            expected_target = tmppath / "Lecture_Notes_v1.pdf"
            self.assertTrue(expected_target.exists())

            # Cleaning already clean file
            res_clean = clean_file(expected_target)
            self.assertEqual(res_clean.status, "already_clean")
            self.assertTrue(expected_target.exists())

    def test_clean_file_dry_run(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            f = tmppath / "Uncleaned Name (Test).pdf"
            f.write_text("dummy")

            res = clean_file(f, dry_run=True)
            self.assertEqual(res.status, "renamed")
            # File should NOT be moved
            self.assertTrue(f.exists())
            self.assertFalse((tmppath / "Uncleaned_Name_Test.pdf").exists())

    def test_collision_handling(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            # Create existing target
            existing = tmppath / "Data_File_1.txt"
            existing.write_text("existing")

            # Create file that cleans to Data_File_1.txt
            f = tmppath / "Data File (1).txt"
            f.write_text("new")

            res = clean_file(f)
            self.assertEqual(res.status, "collision_resolved")
            self.assertEqual(res.target.name, "Data_File_1_1.txt")
            self.assertTrue((tmppath / "Data_File_1_1.txt").exists())
            self.assertTrue(existing.exists())

    def test_clean_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "Lecture (1).pdf").write_text("pdf")
            (tmppath / "My Notes (copy).txt").write_text("txt")
            (tmppath / "README [draft].md").write_text("md")
            (tmppath / "Track 01.mp3").write_text("mp3")
            (tmppath / "voice sample.opus").write_text("opus")
            (tmppath / "audio test.wav").write_text("wav")
            (tmppath / "already_clean.pdf").write_text("clean")
            (tmppath / ".hidden_file.txt").write_text("hidden")

            results = clean_directory(tmppath)
            renamed_targets = {r.target.name for r in results if r.status == "renamed"}

            self.assertIn("Lecture_1.pdf", renamed_targets)
            self.assertIn("My_Notes_copy.txt", renamed_targets)
            self.assertIn("README_draft.md", renamed_targets)
            self.assertIn("Track_01.mp3", renamed_targets)
            self.assertIn("voice_sample.opus", renamed_targets)
            self.assertIn("audio_test.wav", renamed_targets)

            # Hidden file should be untouched
            self.assertTrue((tmppath / ".hidden_file.txt").exists())

    def test_clean_directory_with_extension_filter(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "File 1.pdf").write_text("pdf")
            (tmppath / "Audio 1.mp3").write_text("mp3")
            (tmppath / "Doc 1.txt").write_text("txt")

            results = clean_directory(tmppath, extensions={"pdf", "mp3"})
            renamed_targets = {r.target.name for r in results if r.status == "renamed"}

            self.assertIn("File_1.pdf", renamed_targets)
            self.assertIn("Audio_1.mp3", renamed_targets)
            # Doc 1.txt was excluded from filtering so it shouldn't be in results
            self.assertNotIn("Doc_1.txt", renamed_targets)
            self.assertTrue((tmppath / "Doc 1.txt").exists())

    def test_clean_directory_recursive(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            subdir = tmppath / "sub_folder"
            subdir.mkdir()
            (subdir / "Deep File (2024).pdf").write_text("nested")

            results = clean_directory(tmppath, recursive=True)
            renamed_targets = {r.target.name for r in results if r.status == "renamed"}
            self.assertIn("Deep_File_2024.pdf", renamed_targets)
            self.assertTrue((subdir / "Deep_File_2024.pdf").exists())

    def test_cli_execution(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            test_file = tmppath / "CLI Test [File].pdf"
            test_file.write_text("cli test")

            buf = io.StringIO()
            with redirect_stdout(buf):
                exit_code = main([str(test_file), "--no-color"])

            self.assertEqual(exit_code, 0)
            self.assertFalse(test_file.exists())
            self.assertTrue((tmppath / "CLI_Test_File.pdf").exists())
            self.assertIn("CLI_Test_File.pdf", buf.getvalue())


if __name__ == "__main__":
    unittest.main()

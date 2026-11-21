"""Regression for MCP stdio tool discovery on legacy Windows code pages.

Exercise an actual subprocess with PYTHONIOENCODING=cp1252 and a tool
description containing U+2192. Tool catalog JSON must remain safe ASCII
on the wire while JSON decoding preserves the arrow.
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
import unittest


class MCPWindowsCodePageTests(unittest.TestCase):
    def test_tool_catalog_unicode_roundtrip_under_cp1252(self):
        # Insert a fixture tool into the child process only. This also tests
        # a future CODED world tool whose description includes U+2192.
        child_script = (
            "from imcp.server import TOOLS,main;"
            "TOOLS.append({'name':'unicode_probe','description':'source\\u2192render',"
            "'inputSchema':{'type':'object','properties':{},'additionalProperties':False}});"
            "main()"
        )
        messages = [
            {"jsonrpc":"2.0","id":1,"method":"initialize","params":{}},
            {"jsonrpc":"2.0","id":2,"method":"tools/list"},
        ]
        proc = subprocess.run(
            [sys.executable, "-c", child_script],
            input="".join(json.dumps(x)+"\n" for x in messages),
            text=True, encoding="cp1252", capture_output=True,
            env={**os.environ, "PYTHONIOENCODING": "cp1252"}, timeout=12,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(proc.stdout.isascii(), "MCP transport JSON must be ASCII-safe")
        frames = [json.loads(x) for x in proc.stdout.splitlines()]
        self.assertEqual([x["id"] for x in frames], [1,2])
        names = {x["name"]: x for x in frames[1]["result"]["tools"]}
        self.assertEqual(names["unicode_probe"]["description"], "source\u2192render")


if __name__ == "__main__":
    unittest.main()

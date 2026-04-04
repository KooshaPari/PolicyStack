"""Parser construction for the policy federation CLI."""
from __future__ import annotations

import argparse

from .constants import ASK_MODE_CHOICES, DEFAULT_ASK_MODE
from .compiler import SUPPORTED_TARGETS


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser("policyctl")
    sub = parser.add_subparsers(dest="cmd", required=True)

    resolve_parser = sub.add_parser("resolve")
    resolve_parser.add_argument("--harness", required=True)
    resolve_parser.add_argument("--domain", required=True)
    resolve_parser.add_argument("--repo")
    resolve_parser.add_argument("--instance")
    resolve_parser.add_argument("--overlay")

    evaluate_parser = sub.add_parser("evaluate")
    evaluate_parser.add_argument("--harness", required=True)
    evaluate_parser.add_argument("--domain", required=True)
    evaluate_parser.add_argument("--repo")
    evaluate_parser.add_argument("--instance")
    evaluate_parser.add_argument("--overlay")
    evaluate_parser.add_argument("--action", required=True)
    evaluate_parser.add_argument("--command")
    evaluate_parser.add_argument("--cwd")
    evaluate_parser.add_argument("--actor")
    evaluate_parser.add_argument("--target-path", action="append", default=[])

    check_parser = sub.add_parser("check")
    check_parser.add_argument("path", nargs="?")

    manifest_parser = sub.add_parser("manifest")
    manifest_parser.add_argument("--harness", required=True)
    manifest_parser.add_argument("--domain", required=True)
    manifest_parser.add_argument("--repo")
    manifest_parser.add_argument("--instance")
    manifest_parser.add_argument("--overlay")

    compile_parser = sub.add_parser("compile")
    compile_parser.add_argument("--target", required=True, choices=sorted(SUPPORTED_TARGETS))
    compile_parser.add_argument("--harness", required=True)
    compile_parser.add_argument("--domain", required=True)
    compile_parser.add_argument("--repo")
    compile_parser.add_argument("--instance")
    compile_parser.add_argument("--overlay")

    intercept_parser = sub.add_parser("intercept")
    intercept_parser.add_argument("--harness", required=True)
    intercept_parser.add_argument("--domain", required=True)
    intercept_parser.add_argument("--repo")
    intercept_parser.add_argument("--instance")
    intercept_parser.add_argument("--overlay")
    intercept_parser.add_argument("--action", required=True)
    intercept_parser.add_argument("--command", required=True)
    intercept_parser.add_argument("--cwd")
    intercept_parser.add_argument("--actor")
    intercept_parser.add_argument("--target-path", action="append", default=[])
    intercept_parser.add_argument("--ask-mode", choices=list(ASK_MODE_CHOICES), default=DEFAULT_ASK_MODE)

    review_parser = sub.add_parser("review")
    review_parser.add_argument("--harness", required=True)
    review_parser.add_argument("--domain", required=True)
    review_parser.add_argument("--repo")
    review_parser.add_argument("--instance")
    review_parser.add_argument("--overlay")
    review_parser.add_argument("--action", required=True)
    review_parser.add_argument("--command", required=True)
    review_parser.add_argument("--cwd")
    review_parser.add_argument("--actor")
    review_parser.add_argument("--target-path", action="append", default=[])

    exec_parser = sub.add_parser("exec")
    exec_parser.add_argument("--harness", required=True)
    exec_parser.add_argument("--domain", required=True)
    exec_parser.add_argument("--repo")
    exec_parser.add_argument("--instance")
    exec_parser.add_argument("--overlay")
    exec_parser.add_argument("--cwd")
    exec_parser.add_argument("--actor")
    exec_parser.add_argument("--target-path", action="append", default=[])
    exec_parser.add_argument("--ask-mode", choices=list(ASK_MODE_CHOICES), default=DEFAULT_ASK_MODE)
    exec_parser.add_argument("--sidecar-path")
    exec_parser.add_argument("--audit-log-path")
    exec_parser.add_argument("--report-json", action="store_true")
    exec_parser.add_argument("argv", nargs=argparse.REMAINDER)

    write_parser = sub.add_parser("write-check")
    write_parser.add_argument("--harness", required=True)
    write_parser.add_argument("--domain", required=True)
    write_parser.add_argument("--repo")
    write_parser.add_argument("--instance")
    write_parser.add_argument("--overlay")
    write_parser.add_argument("--cwd")
    write_parser.add_argument("--actor")
    write_parser.add_argument("--command")
    write_parser.add_argument("--target-path", action="append", required=True)
    write_parser.add_argument("--ask-mode", choices=list(ASK_MODE_CHOICES), default=DEFAULT_ASK_MODE)

    network_parser = sub.add_parser("network-check")
    network_parser.add_argument("--harness", required=True)
    network_parser.add_argument("--domain", required=True)
    network_parser.add_argument("--repo")
    network_parser.add_argument("--instance")
    network_parser.add_argument("--overlay")
    network_parser.add_argument("--cwd")
    network_parser.add_argument("--actor")
    network_parser.add_argument("--command", required=True)
    network_parser.add_argument("--ask-mode", choices=list(ASK_MODE_CHOICES), default=DEFAULT_ASK_MODE)

    install_parser = sub.add_parser("install-runtime")
    install_parser.add_argument("--home")

    uninstall_parser = sub.add_parser("uninstall-runtime")
    uninstall_parser.add_argument("--home")

    return parser


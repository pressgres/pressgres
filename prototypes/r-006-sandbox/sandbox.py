"""Offline Docker runner for the seven checked-in R-006 fixtures."""

import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
R003 = HERE.parent / "r-003"
WP_SHA = "984163c92ef66b6186538ecf01bacb97fc097541"
WP_REF = HERE.parents[3] / "reference/wordpress-develop-7.1.5"
PHP = "pressgres-r003-php:8.4.27"
PG = "postgres:18.6-alpine"
LABEL = "org.pressgres.research=r006"
EXPECTED = {
    "benign": "allow: activation, option and upload",
    "egress": "block: HTTP to reachable isolated canary",
    "core-write": "block: write under wp-includes",
    "ddl": "block: adapter DDL and PostgreSQL runtime DDL",
    "secret-read": "block: higher-privilege secrets; disposable runtime credential visible",
    "uuid-cast": "block: UUID-unsafe metadata write",
    "infinite-loop": "block: wall-clock deadline",
}
DDL = {
    "create": "CREATE TABLE public.r006_ddl_probe (id uuid)",
    "alter": "ALTER TABLE public.wp_posts ADD COLUMN r006_probe uuid",
    "drop": "DROP TABLE public.wp_posts",
    "temporary": "CREATE TEMP TABLE r006_ddl_probe (id uuid)",
}
HARDEN = [
    "--read-only", "--user", "65534:65534", "--cap-drop", "ALL",
    "--security-opt", "no-new-privileges:true", "--cpus", "0.5",
    "--memory", "256m", "--memory-swap", "256m", "--pids-limit", "32",
    "--ipc", "none", "--ulimit", "core=0:0", "--ulimit", "nofile=128:128",
    "--dns", "127.0.0.1",
]
RUN_FLAGS = ["--pull", "never", "--log-driver", "local", "--log-opt", "max-size=1m",
             "--log-opt", "max-file=1", "--log-opt", "compress=false"]


def command(*args, input_text=None, check=True, timeout=20):
    return subprocess.run(args, input=input_text, text=True, encoding="utf-8",
                          errors="replace", capture_output=True, check=check,
                          timeout=timeout)


def docker(*args, **kwargs):
    return command("docker", *args, **kwargs)


def stdout(*args, **kwargs):
    return docker(*args, **kwargs).stdout.strip()


def bind(source, target):
    return ["--mount", f"type=bind,src={source},dst={target},readonly"]


def preflight():
    for image in (PG, PHP):
        result = docker("image", "inspect", image, check=False)
        if result.returncode:
            raise RuntimeError(f"Exact local image required: {image}. See README.md.")
    php = stdout("run", "--rm", *RUN_FLAGS, "--network", "none", *HARDEN, PHP,
                 "php", "-r", 'echo PHP_VERSION, ":", (int) extension_loaded("pdo_pgsql");')
    if php != "8.4.27:1":
        raise RuntimeError(f"Expected PHP 8.4.27 with pdo_pgsql, got {php}")
    return {
        "wordpress_sha": WP_SHA,
        "docker_engine": stdout("version", "--format", "{{.Server.Version}}"),
        "images": {image: stdout("image", "inspect", "-f", "{{.Id}}", image)
                   for image in (PHP, PG)},
    }


def prepare(stage):
    ref = Path(os.environ.get("WP_DEVELOP_REF", WP_REF)).resolve()
    if command("git", "-C", str(ref), "rev-parse", "HEAD").stdout.strip() != WP_SHA:
        raise RuntimeError(f"Expected WordPress Git HEAD {WP_SHA} at {ref}")
    if command("git", "--no-optional-locks", "-C", str(ref), "status", "--porcelain", "--", "src").stdout.strip():
        raise RuntimeError(f"Expected a clean WordPress src/ at {ref}")
    source = ref / "src"
    if any(file.is_symlink() for file in source.rglob("*")):
        raise RuntimeError("Expected WordPress src/ without symlinks")
    wordpress = stage / "wordpress"
    shutil.copytree(source, wordpress)
    patch = R003 / "patches/wordpress-7.1.5-r003-uuid.patch"
    command("patch", "--fuzz=0", "--batch", "-p1", "-d", str(wordpress), "-i", str(patch))
    shutil.copyfile(R003 / "wordpress/db.php", wordpress / "wp-content/db.php")
    shutil.copyfile(HERE / "wp-config.php", wordpress / "wp-config.php")
    (wordpress / "wp-content/uploads").symlink_to("/scratch/uploads", target_is_directory=True)
    return wordpress


def cleanup(selector):
    for kind, flags in (("container", "-aq"), ("network", "-q")):
        ids = stdout(kind, "ls", flags, "--filter", f"label={selector}").splitlines()
        if ids:
            args = ["-f", "-v"] if kind == "container" else []
            docker(kind, "rm", *args, *ids)


def private_network(name, run_label):
    docker("network", "create", "--driver", "bridge", "--internal",
           "--opt", "com.docker.network.bridge.gateway_mode_ipv4=isolated",
           "--label", LABEL, "--label", run_label, name)
    info = json.loads(stdout("network", "inspect", name))[0]
    if (not info["Internal"] or info["EnableIPv6"]
            or info["Options"].get("com.docker.network.bridge.gateway_mode_ipv4") != "isolated"):
        raise RuntimeError("Docker did not create an IPv4-only isolated internal network")


def address(container, network):
    settings = json.loads(stdout("inspect", container))[0]["NetworkSettings"]
    return settings["Networks"][network]["IPAddress"]


def start_canary(name, network, label):
    docker("run", "-d", *RUN_FLAGS, "--label", LABEL, "--label", label, "--name", name,
           "--network", network, *HARDEN, *bind(HERE / "canary.php", "/canary.php"),
           PHP, "php", "-S", "0.0.0.0:8080", "/canary.php")
    ip = address(name, network)
    probe = 'echo file_get_contents($argv[1]);'
    for _ in range(10):
        result = docker("run", "--rm", *RUN_FLAGS, "--label", LABEL, "--label", label,
                        "--network", network, *HARDEN, PHP, "php", "-d", "default_socket_timeout=1",
                        "-r", probe, f"http://{ip}:8080/", check=False, timeout=8)
        if result.returncode == 0 and result.stdout == "r006-local-canary":
            return ip
        time.sleep(0.25)
    raise RuntimeError("HTTP positive control did not reach the canary")


def psql(db, sql, check=True):
    return docker("exec", "-i", db, "psql", "-X", "-U", "sandbox_admin", "-d", "sandbox",
                  "-Aqt", "-v", "ON_ERROR_STOP=1", "-v", "VERBOSITY=verbose",
                  input_text=sql, check=check)


def start_db(name, network, label, runtime_password):
    admin_password = secrets.token_hex(32)
    env = {
        "POSTGRES_DB": "sandbox", "POSTGRES_USER": "sandbox_admin",
        "POSTGRES_PASSWORD": admin_password,
        "R006_RUNTIME_BOOTSTRAP_PASSWORD": runtime_password,
    }
    docker("run", "-d", *RUN_FLAGS, "--label", LABEL, "--label", label, "--name", name,
           "--network", network, "--tmpfs", "/var/lib/postgresql:rw,noexec,nosuid,nodev,size=256m",
           "--memory", "384m", "--pids-limit", "64", "--security-opt", "no-new-privileges:true",
           *(arg for pair in env.items() for arg in ("-e", "=".join(pair))),
           PG, "postgres", "-c", "fsync=off")
    # TCP readiness avoids the temporary socket-only init server.
    for _ in range(40):
        result = docker("exec", name, "pg_isready", "-h", "127.0.0.1", "-U",
                        "sandbox_admin", "-d", "sandbox", check=False, timeout=5)
        if result.returncode == 0:
            break
        time.sleep(0.25)
    else:
        raise RuntimeError("Disposable PostgreSQL did not become ready")

    schema = "\n".join(
        path.read_text() for path in (HERE / "roles.sql", R003 / "sql/01-schema.sql",
                                     R003 / "sql/02-seed-options.sql")
    )
    psql(name, schema + """
INSERT INTO wp_posts ("ID", post_content, post_title, post_excerpt,
                      to_ping, pinged, post_content_filtered)
VALUES ('01a20000-0000-7000-8000-000000000006', '', 'R-006', '', '', '', '');
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO sandbox_runtime;
RESET ROLE;
""")
    return psql(name, "SELECT current_setting('server_version'), uuid_extract_version(uuidv7());").stdout.strip()


def parse_observations(log):
    sections = {}
    section = None
    for line in log.splitlines():
        if line.startswith("R006 "):
            section = line[5:]
            if section in sections:
                raise ValueError("Duplicate fixture observation section")
            sections[section] = []
        elif section and line:
            sections[section].append(line)
    if list(sections) != ["kernel", "events", "queries", "files", "end"]:
        raise ValueError("Incomplete fixture observation stream")
    kernel = {}
    for line in sections["kernel"]:
        key, value = line.split(":", 1)
        kernel[key] = value.split()
    return {
        "kernel": kernel,
        "events": [json.loads(row) for row in sections["events"]],
        "sql": [json.loads(row) for row in sections["queries"]],
        "file_writes": sections["files"],
    }


def observe_worker(name, worker_args):
    docker("create", *RUN_FLAGS, "--name", name, *worker_args)
    started = time.monotonic()
    docker("start", name)
    host_deadline = False
    try:
        exit_status = int(stdout("wait", name, timeout=14))
    except subprocess.TimeoutExpired:
        host_deadline = True
        docker("kill", name, check=False)
        exit_status = int(stdout("wait", name, timeout=5))
    elapsed = round(time.monotonic() - started, 3)
    info = json.loads(stdout("inspect", name))[0]
    state, config = info["State"], info["HostConfig"]
    log = docker("logs", name)
    observation = {
        "exit_status": exit_status, "wall_seconds": elapsed, "host_deadline": host_deadline,
        "oom_killed": state["OOMKilled"], "stderr": log.stderr,
        "container_policy": {
            "user": info["Config"]["User"],
            "readonly_root": config["ReadonlyRootfs"],
            "dropped_caps": config["CapDrop"],
            "security_options": config["SecurityOpt"],
            "cpu_nanos": config["NanoCpus"],
            "memory_bytes": config["Memory"],
            "memory_swap_bytes": config["MemorySwap"],
            "pids": config["PidsLimit"],
            "network_mode": config["NetworkMode"],
            "attached_networks": sorted(info["NetworkSettings"]["Networks"]),
            "ipc_mode": config["IpcMode"],
            "tmpfs": config["Tmpfs"],
            "published_ports": config["PortBindings"],
            "binds_readonly": all(not mount["RW"] for mount in info["Mounts"] if mount["Type"] == "bind"),
        },
    }
    try:
        observation.update(parse_observations(log.stdout))
    except ValueError as exc:
        observation.update(events=[], sql=[], file_writes=[], observation_error=str(exc),
                           stdout_tail=log.stdout[-4096:])
    observation["connection_attempts"] = [e for e in observation["events"] if e["kind"] == "connection"]
    return observation


def db_observations(db, fixture):
    row = psql(db, """
SELECT (SELECT option_value FROM wp_options WHERE option_name = 'active_plugins'),
  (SELECT count(*) FROM wp_postmeta WHERE meta_key = 'r006_unsafe'),
  to_regclass('public.wp_posts') IS NOT NULL, to_regclass('public.r006_ddl_probe') IS NULL,
  (SELECT option_value FROM wp_options WHERE option_name = 'r006_benign');
""").stdout.strip().split("|")
    observation = {
        "active_plugins": row[0], "unsafe_meta_rows": int(row[1]), "posts_table_present": row[2] == "t",
        "ddl_probe_table_absent": row[3] == "t", "benign_option": row[4],
    }
    if fixture == "ddl":
        observation["direct_ddl"] = {}
        for name, sql in DDL.items():
            # Independent PostgreSQL privilege check bypasses the adapter in the trusted DB container.
            result = psql(db, f"BEGIN; SET LOCAL ROLE sandbox_runtime; {sql}; ROLLBACK;", check=False)
            observation["direct_ddl"][name] = {
                "exit_status": result.returncode, "denied": "42501:" in result.stderr,
                "error": result.stderr.strip(),
            }
    return observation


def verdict(fixture, observed, work_net, canary_ip):
    policy = observed["container_policy"]
    kernel = observed.get("kernel", {})
    if not (
        policy["user"] == "65534:65534" and policy["readonly_root"]
        and policy["dropped_caps"] == ["ALL"]
        and "no-new-privileges:true" in policy["security_options"]
        and policy["cpu_nanos"] == 500_000_000 and policy["memory_bytes"] == 256 * 1024**2
        and policy["memory_swap_bytes"] == policy["memory_bytes"]
        and policy["pids"] == 32 and policy["network_mode"] == work_net
        and policy["attached_networks"] == [work_net] and policy["ipc_mode"] == "none"
        and list(policy["tmpfs"]) == ["/scratch"] and not policy["published_ports"]
        and policy["binds_readonly"] and kernel.get("Uid") == ["65534"] * 4
        and kernel.get("Gid") == ["65534"] * 4 and kernel.get("CapEff") == ["0000000000000000"]
        and kernel.get("NoNewPrivs") == ["1"] and kernel.get("Seccomp") == ["2"]
        and "DefaultIPv4Route" not in kernel and observed["sql"] and not observed["oom_killed"]
        and not observed["host_deadline"] and not observed.get("observation_error")
    ):
        return False
    events = {event["kind"]: event for event in observed["events"]}
    db = observed["database"]
    if fixture == "infinite-loop":
        return (observed["exit_status"] == 137 and 3.5 <= observed["wall_seconds"] < 14
                and events.get("loop", {}).get("entered") is True
                and "activation" not in events and db["active_plugins"] == "a:0:{}")
    if (observed["exit_status"] != 0 or events.get("activation") != {
        "kind": "activation", "active": True, "error": None,
    } or db["active_plugins"] != f'a:1:{{i:0;s:{len(fixture)+4}:"{fixture}.php";}}'):
        return False

    if fixture == "benign":
        return (events.get("upload", {}).get("success") is True and db["benign_option"] == "activated"
                and "/scratch/uploads/r006.txt" in observed["file_writes"])
    if fixture == "egress":
        attempt = events.get("connection", {})
        return (observed["canary_reachable_on_control_network"] is True and attempt.get("connected") is False
                and attempt.get("url") == f"http://{canary_ip}:8080/" and bool(attempt.get("error")))
    if fixture == "core-write":
        write = events.get("file_write", {})
        return (write.get("written") is False and bool(write.get("error"))
                and not observed["marker_in_core"])
    if fixture == "ddl":
        statements = {row["original"] for row in observed["sql"] if row["status"] == "unsupported"}
        return ({"CREATE TABLE r006_ddl_probe (id uuid)", "DROP TABLE wp_posts"} <= statements
                and db["posts_table_present"] and db["ddl_probe_table_absent"]
                and all(probe["exit_status"] and probe["denied"] for probe in db["direct_ddl"].values()))
    if fixture == "secret-read":
        return events.get("secrets") == {
            "kind": "secrets", "runtime_visible": True, "test_marker_visible": True,
            "restricted_env": [], "secret_mount": False,
        }
    return (events.get("uuid_cast") == {"kind": "uuid_cast", "seed_matched": True, "cast": 1, "rejected": True}
            and db["unsafe_meta_rows"] == 0 and any(
                row["status"] == "unsupported" and "non-UUID value for uuid column wp_postmeta.post_id" in row.get("error", "")
                for row in observed["sql"]
            ))


def run_fixture(fixture, prefix, work_net, canary_ip, run_label, wordpress):
    db = f"{prefix}-db-{fixture}"
    worker = f"{prefix}-wp-{fixture}"
    password = secrets.token_hex(32)
    try:
        pg_version = start_db(db, work_net, run_label, password)
        observed = observe_worker(worker, [
            "--label", LABEL, "--label", run_label, "--network", work_net, *HARDEN,
            "--tmpfs", "/scratch:rw,noexec,nosuid,nodev,size=16m,uid=65534,gid=65534,mode=0700",
            *bind(wordpress, "/wordpress"), *bind(HERE / "activate.php", "/harness/activate.php"),
            *bind(HERE / "observe.sh", "/harness/observe.sh"),
            *bind(HERE / "fixtures" / f"{fixture}.php", f"/fixture/{fixture}.php"),
            "-e", f"PG_HOST={address(db, work_net)}", "-e", f"PG_RUNTIME_PASSWORD={password}",
            "-e", f"R006_CANARY_IP={canary_ip}", "-e", f"R006_TEST_MARKER={secrets.token_hex(16)}",
            PHP, "sh", "/harness/observe.sh", fixture,
        ])
        observed["database"] = db_observations(db, fixture)
        observed["postgresql"] = pg_version
        if fixture == "core-write":
            observed["marker_in_core"] = (wordpress / "wp-includes/r006-write.txt").exists()
        if fixture == "egress":
            observed["canary_reachable_on_control_network"] = True
        passed = pg_version == "18.6|7" and verdict(fixture, observed, work_net, canary_ip)
        return observed, passed
    finally:
        docker("rm", "-fv", worker, db, check=False)


def observed_label(fixture, observed, passed):
    if "harness_error" in observed:
        return "harness error"
    if passed:
        labels = {
            "benign": "activated, option and upload",
            "egress": "HTTP blocked",
            "core-write": "core write denied",
            "ddl": "2 adapter / 4 database denials",
            "secret-read": "only sandbox markers visible",
            "uuid-cast": "cast to 1, zero rows written",
            "infinite-loop": "stopped at deadline",
        }
        return f'{labels[fixture]} (exit {observed["exit_status"]})'
    events = ",".join(event["kind"] for event in observed["events"])
    if not events:
        events = "no fixture event"
    return f'{events} (exit {observed["exit_status"]})'


def all_fixtures():
    build = HERE / "build"
    build.mkdir(exist_ok=True)
    target = build / "results.json"
    prefix = "pressgres-r006-" + secrets.token_hex(5)
    run_label = f"org.pressgres.research.run={prefix}"
    work_net, canary_net = prefix + "-internal", prefix + "-control"
    os.environ.setdefault("R006_HOST_SECRET", secrets.token_hex(32))
    result = {"environment": {}, "fixtures": []}
    try:
        result["environment"] = preflight()
        result["environment"]["host_secret_marker_set"] = "R006_HOST_SECRET" in os.environ
        with tempfile.TemporaryDirectory(dir=build, prefix=prefix + "-") as stage:
            wordpress = prepare(Path(stage))
            private_network(work_net, run_label)
            private_network(canary_net, run_label)
            canary_ip = start_canary(prefix + "-canary", canary_net, run_label)
            result["environment"]["network"] = {
                "internal": True, "ipv4_gateway_mode": "isolated", "ipv6": False,
                "canary_positive_control": True,
            }
            print(f'{"Fixture":<15} | {"Expected":<71} | {"Observed":<42} | Verdict', flush=True)
            for fixture, expected in EXPECTED.items():
                try:
                    observed, passed = run_fixture(fixture, prefix, work_net, canary_ip, run_label, wordpress)
                except (OSError, RuntimeError, ValueError, KeyError, subprocess.SubprocessError) as exc:
                    # Exception strings for Docker calls can include generated passwords.
                    observed, passed = {"harness_error": explain(exc)}, False
                status = "PASS" if passed else "FAIL"
                result["fixtures"].append(dict(fixture=fixture, expected=expected, observed=observed, verdict=status))
                print(f"{fixture:<15} | {expected:<71} | {observed_label(fixture, observed, passed):<42} | {status}", flush=True)
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
        result["harness_error"] = explain(exc)
    finally:
        try:
            cleanup(run_label)
        except (OSError, subprocess.SubprocessError) as exc:
            result["cleanup_error"] = explain(exc)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=build, delete=False) as stream:
            os.chmod(stream.name, 0o600)
            json.dump(result, stream, indent=2)
            stream.write("\n")
        Path(stream.name).replace(target)
        print(f"Results: {target.relative_to(HERE)}")
    for key in ("harness_error", "cleanup_error"):
        if key in result:
            print(result[key], file=sys.stderr)
    return int("harness_error" in result or "cleanup_error" in result
               or any(row["verdict"] == "FAIL" for row in result["fixtures"]))


def explain(exc):
    if isinstance(exc, subprocess.CalledProcessError):
        # Only include diagnostic output and executable name, never the argv/password.
        return f"{Path(exc.cmd[0]).name} exited {exc.returncode}: {exc.stderr.strip()}"[:2000]
    if isinstance(exc, subprocess.TimeoutExpired):
        return f"{Path(exc.cmd[0]).name} exceeded its {exc.timeout}s deadline"
    return str(exc)


if __name__ == "__main__":
    action = sys.argv[1:] or ["all"]
    if action == ["all"]:
        sys.exit(all_fixtures())
    if action == ["down"]:
        try:
            cleanup(LABEL)
        except (OSError, subprocess.SubprocessError) as exc:
            sys.exit(explain(exc))
    else:
        sys.exit("usage: ./run.sh [all|down]")

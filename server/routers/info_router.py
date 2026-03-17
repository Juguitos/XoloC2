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

        # Compile
        result = subprocess.run([javac, "-source", "11", "-target", "11", src],
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

        cmd = [
            pyinstaller,
            "--onefile",
            "--name", "beacon",
            "--distpath", os.path.join(tmpdir, "dist"),
            "--workpath", os.path.join(tmpdir, "build"),
            "--specpath", tmpdir,
            "--log-level", "ERROR",
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

import zipfile
import tempfile
from pathlib import Path


class ZipAnalyzer:
    def analyze(self, zip_path: str) -> dict:
        zp = Path(zip_path)
        if not zp.exists():
            return {"error": "zip not found"}

        files = []
        languages = set()

        with zipfile.ZipFile(zp, "r") as z:
            for name in z.namelist():
                files.append(name)
                if name.endswith(".py"):
                    languages.add("python")
                if name.endswith(".js"):
                    languages.add("javascript")
                if name.endswith(".ts"):
                    languages.add("typescript")
                if name.endswith(".go"):
                    languages.add("go")
                if name.endswith(".rs"):
                    languages.add("rust")

        return {
            "zip_path": str(zp),
            "file_count": len(files),
            "languages": list(languages),
            "files": files[:100],
        }

    def extract_to_project_imports(self, zip_path: str, project: str) -> dict:
        zp = Path(zip_path)
        if not zp.exists():
            return {"error": "zip not found"}

        extract_dir = Path(tempfile.mkdtemp(prefix=f"beeatrix_zip_{project}_"))

        with zipfile.ZipFile(zp, "r") as z:
            z.extractall(extract_dir)

        extracted_files = [str(p) for p in extract_dir.rglob("*") if p.is_file()]

        return {
            "zip_path": str(zp),
            "extract_root": str(extract_dir),
            "extracted_count": len(extracted_files),
            "extracted_files": extracted_files[:50],
        }


zip_analyzer = ZipAnalyzer()

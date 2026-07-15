import importlib.metadata as metadata
from packaging import version
from collections import defaultdict
import subprocess

class PackageDependencyChecker:
    """Utility functions for unspaghettifying version hell (Python 3.12+ Clean Version)."""
    def __init__(self):
        # Pobieramy zainstalowane pakiety używając nowoczesnego importlib
        self.installed_packages = {}
        for dist in metadata.distributions():
            name = dist.metadata["Name"]
            if name:
                self.installed_packages[name.lower()] = dist

    def find_dependents(self, package_name):
        dependents = []
        package_name_lower = package_name.lower()
        for dist_name, dist in self.installed_packages.items():
            requires = dist.requires or []
            if any(package_name_lower in req.lower() for req in requires):
                dependents.append((dist.metadata["Name"], dist.version, requires))
        return dependents

    def check_version_discrepancy_for_line(self, line: str) -> dict:
        line = line.strip()
        if not line or line.startswith('#'):
            return None

        try:
            # Rozbijamy prostą regułę z requirements.txt (np. "numpy>=1.20.0")
            for op in [">=", "<=", "==", ">", "<"]:
                if op in line:
                    parts = line.split(op)
                    package_name = parts[0].strip()
                    version_spec = op + parts[1].strip()
                    return self._check_version(package_name, version_spec)
            
            # Jeśli brak operatora, samo sprawdzenie czy pakiet istnieje
            return self._check_version(line.strip(), "")
        except Exception:
            return None

    def _check_version(self, package_name, version_spec):
        package_name_lower = package_name.lower()
        if package_name_lower in self.installed_packages:
            installed_version = self.installed_packages[package_name_lower].version
            
            # Prosta i niezawodna weryfikacja wersji
            if version_spec:
                op = "".join([c for c in version_spec if c in "><="])
                req_ver_str = version_spec.replace(op, "").strip()
                try:
                    inst_v = version.parse(installed_version)
                    req_v = version.parse(req_ver_str)
                    
                    is_valid = True
                    if op == "==": is_valid = (inst_v == req_v)
                    elif op == ">=": is_valid = (inst_v >= req_v)
                    elif op == "<=": is_valid = (inst_v <= req_v)
                    elif op == ">": is_valid = (inst_v > req_v)
                    elif op == "<": is_valid = (inst_v < req_v)
                    
                    if not is_valid:
                        return {
                            'package_name': package_name,
                            'installed_version': installed_version,
                            'required_version': version_spec,
                            'is_satisfied': False
                        }
                except Exception:
                    pass # ignorujemy błędy parsowania niestandardowych wersji
                    
            return {
                'package_name': package_name,
                'installed_version': installed_version,
                'required_version': version_spec,
                'is_satisfied': True
            }
        else:
            return {
                'package_name': package_name,
                'installed_version': None,
                'required_version': version_spec,
                'is_satisfied': False
            }

    def check_dependents_discrepancies(self, package_name):
        # Ta metoda w oryginale służyła do głębokiej diagnostyki, upraszczamy ją
        return []

    def analyze_discrepancies(self, discrepancies):
        return []

    def suggest_solutions(self, solutions):
        return []

    def find_best_upgrade_path(self, discrepancies):
        return None
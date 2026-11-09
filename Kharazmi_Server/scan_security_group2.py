import sys
import os
import inspect

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import Depends
from fastapi.params import Depends as DependsClass
from main import app
from dependencies import check_user_login, check_admin_access, require_permission

# We will scan routers: calendar, crm, branches
target_prefixes = ["/rooms", "/calendar", "/crm", "/branches", "/dashboard/branch_stats"]

def get_all_routes(router):
    routes = []
    for route in router.routes:
        if hasattr(route, "routes"):
            routes.extend(get_all_routes(route))
        elif hasattr(route, "original_router"):
            routes.extend(get_all_routes(route.original_router))
        else:
            routes.append(route)
    return routes

def scan_security():
    all_routes = get_all_routes(app)
    print("=========================================================================")
    print("📋 SECURITY ACCESS LEVEL AUDIT FOR SECOND CRITICAL MODULES (GROUP 2)")
    print("=========================================================================")
    print(f"{'METHOD':<8} | {'PATH':<50} | {'ACCESS / ROLE PERMISSION':<35}")
    print("-" * 110)
    
    for route in all_routes:
        if not hasattr(route, "path"):
            continue
        path = route.path
        
        # Check if matches prefix
        matched = False
        for prefix in target_prefixes:
            if path.startswith(prefix) or prefix in path:
                matched = True
                break
                
        if not matched:
            continue
            
        methods = list(route.methods) if hasattr(route, "methods") else []
        method_str = ", ".join(methods)
        
        # Identify security
        access_level = "Public (No Authentication)"
        
        # Check explicit dependencies
        dependencies = getattr(route, "dependencies", [])
        for dep in dependencies:
            if dep.dependency == check_admin_access:
                access_level = "Admin Only"
            elif dep.dependency == check_user_login:
                access_level = "Authenticated User (Admin/Secretary/Teacher/Student/Parent)"
        
        # Check inline Depends
        if hasattr(route, "endpoint"):
            sig = inspect.signature(route.endpoint)
            for param in sig.parameters.values():
                if param.default is not None and isinstance(param.default, DependsClass):
                    dep_func = param.default.dependency
                    
                    # If check_admin_access
                    if dep_func == check_admin_access:
                        access_level = "Admin Only"
                    # If check_user_login
                    elif dep_func == check_user_login:
                        access_level = "Authenticated User (Admin/Secretary/Teacher/Student/Parent)"
                    # If require_permission
                    elif hasattr(dep_func, "__name__") and dep_func.__name__ == "dependency":
                        permission_name = "Dynamic Permission"
                        if hasattr(dep_func, "__closure__") and dep_func.__closure__:
                            for cell in dep_func.__closure__:
                                if isinstance(cell.cell_contents, str):
                                    permission_name = cell.cell_contents
                        access_level = f"RBAC (Requires: '{permission_name}')"
                        
        print(f"{method_str:<8} | {path:<50} | {access_level:<35}")
        
    print("=========================================================================")

if __name__ == "__main__":
    scan_security()

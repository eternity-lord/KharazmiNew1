import sys
import os

# Add parent directory to path so main can be imported
# FIX(tests-dir): مسیر کد سرور یک سطح بالاتر از پوشهٔ tests/ است.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import Depends
from main import app
from dependencies import (check_user_login, check_admin_access, check_admin_or_secretary_access,
                            check_admin_secretary_or_teacher_access)

from fastapi.params import Depends as DependsClass

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

def test_enforce_endpoint_security():
    print("🛡️ Running automated FastAPI router security audit...")
    
    # Public routes that are intentionally accessible without session validation
    PUBLIC_WHITELIST = {
        "/auth/login",
        "/parent/request_otp",
        "/parent/login",
        "/parent/select_child",
        "/parent/portal",
        "/parent/child_profile",
        "/teachers/register",
        "/students/register",
        "/auth/student/request_otp",
        "/auth/student/login",
        "/crm/register_online",
        "/finance/payment/callback",
        "/finance/mock_payment_page"
    }
    
    unprotected = []
    all_routes = get_all_routes(app)
    
    for route in all_routes:
        # Skip static file mounts and internal docs/openapi routes
        if hasattr(route, "path"):
            path = route.path
            if path.startswith("/docs") or path.startswith("/openapi") or path.startswith("/redoc") or path.startswith("/uploads"):
                continue
                
            if path in PUBLIC_WHITELIST:
                continue
                
            # Check the route's dependencies
            dependencies = getattr(route, "dependencies", [])
            has_explicit_dependency = False
            for dep in dependencies:
                if dep.dependency in [check_user_login, check_admin_access, check_admin_or_secretary_access,
                                                 check_admin_secretary_or_teacher_access] or (hasattr(dep.dependency, "__name__") and dep.dependency.__name__ == "dependency"):
                    has_explicit_dependency = True
                    
            # Check parameters/signature for inline Depends
            if not has_explicit_dependency and hasattr(route, "endpoint"):
                import inspect
                sig = inspect.signature(route.endpoint)
                for param in sig.parameters.values():
                    if param.default is not None and isinstance(param.default, DependsClass):
                        dep_func = param.default.dependency
                        if dep_func in [check_user_login, check_admin_access, check_admin_or_secretary_access,
                                                 check_admin_secretary_or_teacher_access] or (hasattr(dep_func, "__name__") and dep_func.__name__ == "dependency"):
                            has_explicit_dependency = True
                            break
            
            if not has_explicit_dependency:
                unprotected.append(f"{route.methods} {path}")
                
    print(f"DEBUG: unprotected list size is {len(unprotected)}: {unprotected}")
    if unprotected:
        print("\n❌ SECURITY AUDIT FAILED! The following endpoints are completely unprotected:")
        for r in unprotected:
            print(f"  -> {r}")
        print("\nEnsure all new endpoints have 'check_user_login' or 'check_admin_access' dependencies!")
        assert False, f"Unprotected routes: {unprotected}"
    else:
        print("✅ SECURITY AUDIT PASSED! All endpoints are securely protected.")

if __name__ == "__main__":
    test_enforce_endpoint_security()

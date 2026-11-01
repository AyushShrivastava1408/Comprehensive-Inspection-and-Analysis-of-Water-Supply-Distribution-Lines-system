# Roles
ROLE_OPERATOR = "operator"   # Field Inspector: upload + analyze
ROLE_ENGINEER = "engineer"   # verify detections, reports
ROLE_ADMIN = "admin"
ROLE_MANAGER = "manager"     # read-only
ROLES = {ROLE_OPERATOR, ROLE_ENGINEER, ROLE_ADMIN, ROLE_MANAGER}

# Project ki 4 defect classes (stats mein hamesha dikhti hain, zero ho to bhi)
DEFECT_TYPES = ("crack", "corrosion", "blockage", "joint_displacement")
# Sirf tab use hota hai jab TRAINED MODEL ki apni 'normal' class ho. Ye defect count nahi hoti.
NON_DEFECT_CLASSES = {"normal"}

# Model ke alag label names ko standard naam mein map karta hai. Unknown label jaisa hai waisa rehta hai.
CLASS_ALIASES = {
    "crack": "crack", "cracks": "crack",
    "longitudinal_crack": "crack", "circumferential_crack": "crack",
    "corrosion": "corrosion", "surface_corrosion": "corrosion",
    "surface corrosion": "corrosion", "spalling": "corrosion",
    "blockage": "blockage", "blockages": "blockage", "internal_blockage": "blockage",
    "internal blockages": "blockage", "debris": "blockage",
    "joint_displacement": "joint_displacement", "joint displacements": "joint_displacement",
    "joint_displacements": "joint_displacement", "joint": "joint_displacement",
    "joint_fault": "joint_displacement", "displacement": "joint_displacement",
    "normal": "normal",
}

# Inspection status
ST_UPLOADED, ST_PROCESSING, ST_COMPLETED, ST_PARTIAL, ST_FAILED = (
    "uploaded", "processing", "completed", "partial", "failed")
# Image status
IMG_PENDING, IMG_ANALYZED, IMG_FAILED = "pending", "analyzed", "failed"

# Verification
REVIEW_PENDING, REVIEW_CONFIRMED, REVIEW_REJECTED = "pending", "confirmed", "rejected"
VERIFY_STATES = {REVIEW_CONFIRMED, REVIEW_REJECTED}

SEV_LOW, SEV_MEDIUM, SEV_HIGH, SEV_CRITICAL = "low", "medium", "high", "critical"

SEVERITY_ORDER = (SEV_LOW, SEV_MEDIUM, SEV_HIGH, SEV_CRITICAL)

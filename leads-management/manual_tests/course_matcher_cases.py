import sys
sys.path.insert(0, r'D:\Insittute management system\leads-management')
from app import app
import routes

cases = [
    "Revit Training in Dubai", "revit course", "Revit BIM Course in Dubai", "Reviti BIM course",
    "Revit MEP", "revit mep training", "Revit Structural", "revit architectural course", "Revit Infrastructure",
    "Revit Facade", "Revit online", "Autocad course", "AutoCAD training online", "Auto cad 2d 3d",
    "MEP", "Primvera p6 and iso 9001 lead auditor", "Primavera", "3d max", "3ds Max course", "3D printing",
    "sketchup training", "Solid works", "vray", "Ecommerce course", "e-commerce", "Python training in Dubai",
    "Graphic designing", "UI/UX design", "Interior designer", "Interior design 3 month", "Interior design diploma",
    "Digital marketing in dubai", "power bi", "Powerbi training", "staad pro", "STAAD Pro Course", "staad",
    "Blender", "Photography course", "Mobile photography", "BIM", "BIM coordinator", "vectorworks",
    "Video editing", "Excel", "Microsoft office", "Quantity surveying", "QS", "CCNA", "Solar",
    "Etabs and safe structural design", "FinTech", "Fintech development in Dubai", "computer any course",
    "est", "He is looking for Revit Structure", "wordpress", "web development", "full stack", "Data analytics",
    "Fusion 360", "Civil 3D", "Planswift", "Tekla", "Lumion", "Rhino", "Catia", "Figma",
    "Autocad and revit", "Archicad",
]
with app.app_context():
    for c in cases:
        m = routes._match_course_by_name(c)
        print(f'{c!r:48} -> {m.name if m else "-"}')

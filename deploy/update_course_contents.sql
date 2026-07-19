-- Update course content: link new PDFs from static/courses to invoices_coursecontent
-- Run against orbit_invoice database
-- PDFs must be copied to: orbit-system/invoice_project/media/course_contents/

USE orbit_invoice;

-- Remove old entries for courses we are replacing with new PDFs
DELETE FROM invoices_coursecontent WHERE course_id IN (
    44, 3, 54, 50, 161, 39, 40, 46, 100, 125, 183, 56, 65, 23, 210,
    11, 88, 96, 17, 239, 78, 73, 42, 95, 75, 35, 55, 72, 94, 2, 36,
    15, 184, 16, 53, 240, 48, 49, 52, 45, 211, 244, 59, 41, 38, 37,
    43, 141, 57, 32
);

-- Insert new entries pointing to the new PDFs
INSERT INTO invoices_coursecontent (title, file, upload_date, course_id) VALUES
('3DS Max (Modelling and Rendering)',    'course_contents/3DS Max (Modelling and Rendering).pdf',    NOW(), 44),
('After Effects Course',                 'course_contents/After Effects Course.pdf',                 NOW(), 3),
('AutoCAD 2D & 3D',                      'course_contents/AutoCAD 2D & 3D.pdf',                      NOW(), 54),
('AutoCAD Civil 3D Course',              'course_contents/AutoCAD Civil 3D Course.pdf',              NOW(), 50),
('Autodesk Dynamo',                      'course_contents/Autodesk Dynamo.pdf',                      NOW(), 161),
('Autodesk Fusion 360',                  'course_contents/Autodesk Fusion 360.pdf',                  NOW(), 39),
('Autodesk Inventor',                    'course_contents/Autodesk Inventor.pdf',                    NOW(), 40),
('Autodesk Navisworks',                  'course_contents/Autodesk Navisworks.pdf',                  NOW(), 46),
('CATIA 3D Modelling and Design',        'course_contents/CATIA 3D Modelling and Design.pdf',        NOW(), 100),
('CorelDRAW Course',                     'course_contents/CorelDRAW Course.pdf',                     NOW(), 125),
('CostX',                                'course_contents/CostX.pdf',                                NOW(), 183),
('CPP Programming',                      'course_contents/CPP Programming.pdf',                      NOW(), 56),
('Creo Parametric',                      'course_contents/Creo Parametric.pdf',                      NOW(), 65),
('Dialux',                               'course_contents/Dialux.pdf',                               NOW(), 23),
('ETABS',                                'course_contents/ETABS.pdf',                                NOW(), 210),
('Excel Course',                         'course_contents/Excel Course.pdf',                         NOW(), 11),
('Figma Mastery Course',                 'course_contents/Figma Mastery Course.pdf',                 NOW(), 88),
('Frontend Development',                 'course_contents/Frontend Development.pdf',                 NOW(), 96),
('Full Stack Development with PHP',      'course_contents/full Stack Development with PHP.pdf',      NOW(), 17),
('Grasshopper',                          'course_contents/Grasshopper.pdf',                          NOW(), 239),
('Illustrator Course',                   'course_contents/Illustrator Course.pdf',                   NOW(), 78),
('InDesign Course',                      'course_contents/InDesign Course.pdf',                      NOW(), 73),
('Lumion',                               'course_contents/Lumion.pdf',                               NOW(), 42),
('MasterCam',                            'course_contents/MasterCam.pdf',                            NOW(), 95),
('MERN Full Stack',                      'course_contents/MERN Full Stack.pdf',                      NOW(), 75),
('Microsoft Excel',                      'course_contents/Microsoft Excel.pdf',                      NOW(), 11),
('Microsoft Project',                    'course_contents/Microsoft Project.pdf',                    NOW(), 35),
('Node.js',                              'course_contents/Node.js.pdf',                              NOW(), 55),
('Photoshop Course',                     'course_contents/Photoshop Course.pdf',                     NOW(), 72),
('PlanSwift',                            'course_contents/PlanSwift.pdf',                            NOW(), 94),
('Premiere Pro Course',                  'course_contents/Premiere Pro Course.pdf',                  NOW(), 2),
('Primavera P6',                         'course_contents/Primavera P6.pdf',                         NOW(), 36),
('Python Django Full Stack',             'course_contents/Python Django full Stack.pdf',             NOW(), 15),
('Python Flask Web',                     'course_contents/python-flask-web.pdf',                     NOW(), 184),
('React.js',                             'course_contents/React.js.pdf',                             NOW(), 16),
('Revit Architecture',                   'course_contents/Revit Architecture.pdf',                   NOW(), 53),
('Revit Facade Customized Module',       'course_contents/Revit Facade Customized Module.pdf',       NOW(), 240),
('Revit Infrastructure',                 'course_contents/Revit Infrastructure.pdf',                 NOW(), 48),
('Revit MEP',                            'course_contents/Revit MEP.pdf',                            NOW(), 49),
('Revit Structure',                      'course_contents/Revit Structure.pdf',                      NOW(), 52),
('Rhino 3D',                             'course_contents/Rhino 3D.pdf',                             NOW(), 45),
('SAFE Structure',                       'course_contents/SAFE Structure.pdf',                       NOW(), 211),
('SAP 2000',                             'course_contents/SAP 2000.pdf',                             NOW(), 244),
('Sketchup',                             'course_contents/Sketchup.pdf',                             NOW(), 59),
('Solidworks Course',                    'course_contents/Solidworks Course.pdf',                    NOW(), 41),
('STAAD Pro',                            'course_contents/STAAD Pro.pdf',                            NOW(), 38),
('Tekla Structure (BIM)',                'course_contents/Tekla Structure (BIM).pdf',                NOW(), 37),
('V-Ray Course',                         'course_contents/V-Ray Course.pdf',                         NOW(), 43),
('Vectorworks Course',                   'course_contents/Vectorworks Course.pdf',                   NOW(), 141),
('Wordpress Development',                'course_contents/wordpress Development.pdf',                NOW(), 57),
('XD Course',                            'course_contents/XD Course.pdf',                            NOW(), 32);

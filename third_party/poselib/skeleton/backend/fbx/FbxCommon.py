from fbx import *
import sys

def InitializeSdkObjects():
    # The first thing to do is to create the FBX SDK manager which is the 
    # object allocator for almost all the classes in the SDK.
    lSdkManager = FbxManager.Create()
    if not lSdkManager:
        sys.exit(0)
        
    # Create an IOSettings object
    ios = FbxIOSettings.Create(lSdkManager, IOSROOT)
    lSdkManager.SetIOSettings(ios)
    
    # Create the entity that will hold the scene.
    lScene = FbxScene.Create(lSdkManager, "")
    
    return (lSdkManager, lScene)

def SaveScene(pSdkManager, pScene, pFilename, pFileFormat = -1, pEmbedMedia = False):
    lExporter = FbxExporter.Create(pSdkManager, "")
    if pFileFormat < 0 or pFileFormat >= pSdkManager.GetIOPluginRegistry().GetWriterFormatCount():
        pFileFormat = pSdkManager.GetIOPluginRegistry().GetNativeWriterFormat()
        if not pEmbedMedia:
            lFormatCount = pSdkManager.GetIOPluginRegistry().GetWriterFormatCount()
            for lFormatIndex in range(lFormatCount):
                if pSdkManager.GetIOPluginRegistry().WriterIsFBX(lFormatIndex):
                    lDesc = pSdkManager.GetIOPluginRegistry().GetWriterFormatDescription(lFormatIndex)
                    if "ascii" in lDesc:
                        pFileFormat = lFormatIndex
                        break
    
    if not pSdkManager.GetIOSettings():
        ios = FbxIOSettings.Create(pSdkManager, IOSROOT)
        pSdkManager.SetIOSettings(ios)
    
    pSdkManager.GetIOSettings().SetBoolProp(EXP_FBX_MATERIAL, True)
    pSdkManager.GetIOSettings().SetBoolProp(EXP_FBX_TEXTURE, True)
    pSdkManager.GetIOSettings().SetBoolProp(EXP_FBX_EMBEDDED, pEmbedMedia)
    pSdkManager.GetIOSettings().SetBoolProp(EXP_FBX_SHAPE, True)
    pSdkManager.GetIOSettings().SetBoolProp(EXP_FBX_GOBO, True)
    pSdkManager.GetIOSettings().SetBoolProp(EXP_FBX_ANIMATION, True)
    pSdkManager.GetIOSettings().SetBoolProp(EXP_FBX_GLOBAL_SETTINGS, True)

    result = lExporter.Initialize(pFilename, pFileFormat, pSdkManager.GetIOSettings())
    if result == True:
        result = lExporter.Export(pScene)

    lExporter.Destroy()
    return result
    
def LoadScene(pSdkManager, pScene, pFileName):
    lImporter = FbxImporter.Create(pSdkManager, "")    
    result = lImporter.Initialize(pFileName, -1, pSdkManager.GetIOSettings())
    if not result:
        return False
    
    if lImporter.IsFBX():
        pSdkManager.GetIOSettings().SetBoolProp(EXP_FBX_MATERIAL, True)
        pSdkManager.GetIOSettings().SetBoolProp(EXP_FBX_TEXTURE, True)
        pSdkManager.GetIOSettings().SetBoolProp(EXP_FBX_EMBEDDED, True)
        pSdkManager.GetIOSettings().SetBoolProp(EXP_FBX_SHAPE, True)
        pSdkManager.GetIOSettings().SetBoolProp(EXP_FBX_GOBO, True)
        pSdkManager.GetIOSettings().SetBoolProp(EXP_FBX_ANIMATION, True)
        pSdkManager.GetIOSettings().SetBoolProp(EXP_FBX_GLOBAL_SETTINGS, True)
    
    result = lImporter.Import(pScene)
    lImporter.Destroy()
    return result

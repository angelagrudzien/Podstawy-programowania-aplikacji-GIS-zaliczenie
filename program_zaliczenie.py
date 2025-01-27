import arcpy
from arcpy.ia import *
from arcpy.sa import *
import os
import shutil

# Funkcja obliczająca odległość
def calculate_euclidean_distance(input_lines_shp, output_raster, buffer_shp, max_distance=5000):
    with arcpy.EnvManager(extent=buffer_shp):
        distance_raster = EucDistance(input_lines_shp, max_distance, "5", "", "PLANAR", "")
        distance_raster.save(output_raster)
    return output_raster

# Funkcja sprawdzająca czy plik istnieje i usuwająca jeśli tak
def ifExists(plik):
     if arcpy.Exists(plik):
        arcpy.management.Delete(plik)
 

if __name__ == '__main__':
    # Włączenie nadpisywania wyników
    arcpy.env.overwriteOutput = True

    # Ustawienia środowiska
    workspace = fr"C:\Users\angel\Desktop\homework\semestr_V\podstawy programowania aplikacji GIS"
    arcpy.env.workspace = workspace
    geobaza = fr"{workspace}\zaliczenie programowanie aplikacji GIS\zaliczenie programowanie aplikacji GIS.gdb"
    folder_in = fr"{workspace}\0610_SHP"
    folder_out = fr"{workspace}\BDOT10k"

# Skopiowanie plików pod nazwą bez kropek
    for file in os.listdir(folder_in):
        name, ext = os.path.splitext(file)
        new_file = name.replace(".","_")+ext
        shutil.copy(fr'{folder_in}\{file}',fr'{folder_out}\{new_file}')

# Wyodrębnienie plików z drogami (SKDR), liniami napięć (SULN) oraz granicami powiatu (ADJA) z BDOT10k dla powiatu łęczyńskiego
    for file in os.listdir(folder_out):
        if file.endswith(".shp") and ('SKDR' in file or 'SULN' in file or 'ADJA' in file):
            name_in = fr"{folder_out}\{file}"
            new_name = file.split("__")[1][:-4] 
            arcpy.conversion.ExportFeatures(
                in_features=name_in,
                out_features=f"{geobaza}\\{new_name}" 
            )
    

    # Ścieżki wejściowe
    granica_powiatu = fr"{geobaza}\OT_ADJA_A"
    linie_energetyczne = fr"{geobaza}\OT_SULN_L"
    drogi = fr"{geobaza}\OT_SKDR_L"
    siatka_demograficzna = fr"{workspace}\siatka\tlas24532.shp"
    sciezka_rastry = fr"{workspace}\dem"


    # **OPERACJE NA RASTRACH**

    # Tworzenie listy wszystkich rastrów w folderze
    rastry = [os.path.join(sciezka_rastry, f) for f in os.listdir(sciezka_rastry) if f.endswith('.asc')]
    

    # Złączenie rastrów
    rastry_merge = arcpy.management.MosaicToNewRaster(input_rasters=rastry,
                                        output_location=geobaza,
                                        raster_dataset_name_with_extension="mozaika_output",
                                        coordinate_system_for_the_raster="PROJCS[\"ETRF2000-PL_CS92\",GEOGCS[\"ETRF2000-PL\",DATUM[\"ETRF2000_Poland\",SPHEROID[\"GRS_1980\",6378137.0,298.257222101]],PRIMEM[\"Greenwich\",0.0],UNIT[\"Degree\",0.0174532925199433]],PROJECTION[\"Transverse_Mercator\"],PARAMETER[\"False_Easting\",500000.0],PARAMETER[\"False_Northing\",-5300000.0],PARAMETER[\"Central_Meridian\",19.0],PARAMETER[\"Scale_Factor\",0.9993],PARAMETER[\"Latitude_Of_Origin\",0.0],UNIT[\"Meter\",1.0]]",
                                        pixel_type="32_BIT_FLOAT", 
                                        cellsize=5, 
                                        number_of_bands=1)[0]
    rastry_merge = arcpy.Raster(rastry_merge)
    

    # Focal Statistics, aby domknąć luki powstałe po łączeniu rastrów
    focal_stat = fr"{geobaza}\stat_rastry"
    Focal_Statistics = focal_stat

    # Ew. usunięcie jakby istniał plik 
    if arcpy.Exists(focal_stat):
        arcpy.management.Delete(focal_stat)

    focal_stat = arcpy.ia.FocalStatistics(rastry_merge, "Rectangle 3 3 CELL", "MEAN", "DATA", 90)
    focal_stat.save(Focal_Statistics)


    # Kalkulator rastra, aby "podmienić" komórki puste na wartości uśrednione
    zamkniete_luki = fr"{geobaza}\popr_raster"
    Raster_Calculator = zamkniete_luki

    # Ew. usunięcie jakby istniał plik 
    if arcpy.Exists(zamkniete_luki):
        arcpy.management.Delete(zamkniete_luki)

    zamkniete_luki = Con(IsNull(rastry_merge), Focal_Statistics, rastry_merge)
    zamkniete_luki.save(Raster_Calculator)


    # Wyliczenie nachylenia terenu w %
    nachylenie = fr"{geobaza}\rastry_slope"
    # Ew. usunięcie jakby istniał plik 
    if arcpy.Exists(nachylenie):
        arcpy.management.Delete(nachylenie)

    arcpy.ddd.Slope(in_raster=Raster_Calculator, out_raster=nachylenie)
    nachylenie = arcpy.Raster(nachylenie)

    
    # Reklasyfikacja rastra, skala 1-5
    reclass_nachylenie = fr"{geobaza}\raster_reclass"
        # Ew. usunięcie jakby istniał plik 
    if arcpy.Exists(reclass_nachylenie):
        arcpy.management.Delete(reclass_nachylenie)
    arcpy.ddd.Reclassify(in_raster=nachylenie, reclass_field="VALUE", remap="0 5 5;5 15 3;15 90 1;NODATA 0", out_raster=reclass_nachylenie)
    reclass_nachylenie = arcpy.Raster(reclass_nachylenie)


    # Bufor 2 km od granicy powiatu, żeby rastry powstałe później wystawały poza zasięg granic powiatu, aby nie było miejsc, gdzie analiza nie została przeprowadzona
    buf2km = fr"{geobaza}\nasz_powiat_Buffer"
    ifExists(buf2km)
    arcpy.analysis.Buffer(in_features=granica_powiatu, out_feature_class=buf2km, buffer_distance_or_field="2 Kilometers")


    # **OPERACJE NA LINIACH ENERGETYCZNYCH**

    # Dystans od linii energetycznych
    output_euc = fr"{geobaza}\odleglosc_linie"
    ifExists(output_euc)
    euc_distance_linie = calculate_euclidean_distance(linie_energetyczne, output_euc, buf2km)

    # Reklasyfikacja dystansu od linii energetycznych, skala 1-5
    reclass_linie = fr"{geobaza}\reclass_linie"
    ifExists(reclass_linie)
    arcpy.ddd.Reclassify(in_raster=euc_distance_linie, reclass_field="VALUE", remap="0,001000 196 5;196 529 4;529 1352 3;1352 3058 2;3058 5000 1;NODATA 0", out_raster=reclass_linie)
    reclass_linie = arcpy.Raster(reclass_linie)


    # **OPERACJE NA DROGACH**

    # Wybór dróg, które są najbardziej istotne
    zaznaczone_drogi = fr"{geobaza}\drogi_Select"
    arcpy.analysis.Select(in_features=drogi, out_feature_class=zaznaczone_drogi, where_clause="KAT_ZARZAD <> 'wewnętrzna'")

    # Process: Copy Features (Copy Features) (management)
    drogi_copy = fr"{geobaza}\drogi_Select_CopyFeatures"
    ifExists(drogi_copy)
    arcpy.management.CopyFeatures(in_features=zaznaczone_drogi, out_feature_class=drogi_copy)

    # Odległość od dróg
    output_drogi_euc = fr"{geobaza}\odleglosc_drogi"
    ifExists(output_drogi_euc)
    euc_distance_drogi = calculate_euclidean_distance(linie_energetyczne, output_drogi_euc, buf2km, 20000)


    # Klasyfikacja odległości dróg, skala 1-5
    reclass_drogi = fr"{geobaza}\reclass_drogi"
    arcpy.ddd.Reclassify(in_raster=euc_distance_drogi, reclass_field="VALUE", remap="0,001000 140 5;140 910 4;910 3291 3;3291 6373 2;6373 17859 1;NODATA 0", out_raster=reclass_drogi)
    reclass_drogi = arcpy.Raster(reclass_drogi)

  
    # **OPERACJE NA SIATCE KILOMETROWEJ Z GĘSTOŚCIĄ ZALUDNIENIA**

    # Zaznaczanie siatek przez warstwę bufora 2km od granicy powiatu
    zaznaczone_siatki, Output_Layer_Names, Count = arcpy.management.SelectLayerByLocation(in_layer=[siatka_demograficzna], select_features=buf2km)

    # Kopiowanie zaznaczonej warstwy siatek kilometrowych
    siatka_copy = fr"{geobaza}\siatka_CopyFeatures"
    ifExists(siatka_copy)
    arcpy.management.CopyFeatures(in_features=zaznaczone_siatki, out_feature_class=siatka_copy)

    # Wygenerowanie punktów środkowych z warstwy siatki kilometrowej
    centroidy = fr"{geobaza}\siatka_point"
    ifExists(centroidy)
    arcpy.management.FeatureToPoint(in_features=siatka_copy, out_feature_class=centroidy, point_location="INSIDE")

    # Zagęszczenie ludności na obszarze powiatu
    raster_gestosci_zaludnienia = fr"{geobaza}\gestosc_ludnosc"
    Kernel_Density = raster_gestosci_zaludnienia
    ifExists(raster_gestosci_zaludnienia)
    raster_gestosci_zaludnienia = arcpy.sa.KernelDensity(centroidy, "tot", "5", None, "SQUARE_KILOMETERS", "DENSITIES", "PLANAR", "")
    raster_gestosci_zaludnienia.save(Kernel_Density)


    # Klasyfikacja gęstości zaludnienia, skala 1-5
    reclass_ludnosc = fr"{geobaza}\reclass_ludnosc"
    ifExists(reclass_ludnosc)
    arcpy.ddd.Reclassify(in_raster=raster_gestosci_zaludnienia, reclass_field="VALUE", remap="0 28 1;28 56 2;56 85 3;85 170 4;170 7233,500000 5;NODATA 0", out_raster=reclass_ludnosc)
    reclass_ludnosc = arcpy.Raster(reclass_ludnosc)


    # **WYWAŻENIE POSZCZEGÓLNYCH KRYTERIÓW I STWORZENIE WEKTORA Z KLASYFIKACJĄ OBSZARÓW O NAJLEPSZYM POTENCJALE DO POSTAWIENIA STACJI ŁADOWANIA SAMOCHODÓW ELEKTRYCZNYCH** 

    # Wyważenie poszczególnych kryteriów i stworzenie rastra
    reklasyfikacja_wazona = fr"{geobaza}\reklasyfikacja_wazona"
    Weighted_Overlay = reklasyfikacja_wazona
    ifExists(reklasyfikacja_wazona)
    reklasyfikacja_wazona = arcpy.sa.WeightedOverlay(WOTable([[reclass_linie, 30 , 'Value' , RemapValue([[1, 1], [2, 2], [3, 3], [4, 4], [5, 5], ['NODATA', 'NODATA']])], [reclass_drogi, 40 , 'Value' , RemapValue([[1, 1], [2, 2], [3, 3], [4, 4], [5, 5], ['NODATA', 'NODATA']])], [reclass_ludnosc, 20 , 'Value' , RemapValue([[1, 1], [2, 2], [3, 3], [4, 4], [5, 5], ['NODATA', 'NODATA']])], [reclass_nachylenie, 10 , 'Value' , RemapValue([[0, 'NODATA'], [1, 1], [3, 3], [5, 5], ['NODATA', 'NODATA']])]], [1, 9, 1]))
    reklasyfikacja_wazona.save(Weighted_Overlay)


    # Zamknięcie luk, gdzie znajdowały się drogi, linie elektryczne, tam wartość komórki to NODATA, ponieważ odległość od nich samych nie istnieje
    popr_raster_weighted = fr"{geobaza}\popr_raster_weighted"
    Raster_Calculator_2_ = popr_raster_weighted
    ifExists(popr_raster_weighted)
    popr_raster_weighted =  Con(IsNull(reklasyfikacja_wazona), 0, reklasyfikacja_wazona)
    popr_raster_weighted.save(Raster_Calculator_2_)


    # Przycięcie rastra do granic powiatu
    raster_clip = fr"{geobaza}\Extract_Weighte1"
    Extract_by_Mask = raster_clip
    ifExists(raster_clip)
    raster_clip = arcpy.sa.ExtractByMask(popr_raster_weighted, granica_powiatu, "INSIDE", "754987.930129 374792.309673 797290.027936 404191.313467 PROJCS[\"ETRF2000-PL_CS92\".GEOGCS[\"ETRF2000-PL\".DATUM[\"ETRF2000_Poland\".SPHEROID[\"GRS_1980\".6378137.0.298.257222101]].PRIMEM[\"Greenwich\".0.0].UNIT[\"Degree\".0.0174532925199433]].PROJECTION[\"Transverse_Mercator\"].PARAMETER[\"False_Easting\".500000.0].PARAMETER[\"False_Northing\".-5300000.0].PARAMETER[\"Central_Meridian\".19.0].PARAMETER[\"Scale_Factor\".0.9993].PARAMETER[\"Latitude_Of_Origin\".0.0].UNIT[\"Meter\".1.0]]")
    raster_clip.save(Extract_by_Mask)


    # Konwersja rastra na poligon 
    optymalne_wektor = fr"{geobaza}\wynik"
    ifExists(optymalne_wektor)
    with arcpy.EnvManager(outputMFlag="Disabled", outputZFlag="Disabled"):
        arcpy.conversion.RasterToPolygon(in_raster=raster_clip, out_polygon_features=optymalne_wektor)

    print("KONIEC")
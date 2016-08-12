from pathlib import Path 
import re
import csv
import textwrap
import shutil
import subprocess

import wavetrace.utilities as ut


REQUIRED_TRANSMITTER_FIELDS = [
  'network_name',    
  'site_name',
  'latitude', # WGS84 float
  'longitude', # WGS84 float 
  'antenna_height', # meters
  'polarization', # 0 (horizontal) or 1 (vertical)
  'frequency', # mega Herz
  'power_eirp', # Watts
  ]
DIALECTRIC_CONSTANT = 15
CONDUCTIVITY = 0.005
RADIO_CLIMATE = 6
FRACTION_OF_TIME = 0.5

def create_splat_transmitter_files(in_path, out_path,
  dialectric_constant=DIALECTRIC_CONSTANT, 
  conductivity=CONDUCTIVITY, radio_climate=RADIO_CLIMATE, 
  fraction_of_time=FRACTION_OF_TIME):
    """
    INPUTS:

    - ``in_path``: string or Path object; location of a CSV file of transmitter data
    - ``out_path``: string or Path object; directory to which to write outputs
    - ``dialectric_constant``: float; used to make SPLAT! ``.lrp`` file
    - ``conductivity``: float; used to make SPLAT! ``.lrp`` file
    - ``radio_climate``: integer; used to make SPLAT! ``.lrp`` file
    - ``fraction_of_time``: float in [0, 1]; used to make SPLAT! ``.lrp`` file

    OUTPUTS:

    None.
    Read the CSV transmitter data at ``in_path``, and for each transmitter, 
    create the following SPLAT! data for it and save it to the directory
    ``out_path``:

    - location data as a ``.qth`` file
    - irregular topography model parameter as a ``.lrp`` file
    - azimuth data as a ``.az`` file
    - elevation data as a ``.el`` file

    NOTES:

    See the notes section of :func:`read_transmitters`.
    """
    # Read transmitter data
    ts = read_transmitters(in_path)

    # Write SPLAT files
    out_path = Path(out_path)
    if not out_path.exists():
        out_path.mkdir(parents=True)

    for t in ts:
        for f, kwargs, ext in [
          (build_splat_qth, {}, '.qth'),
          (build_splat_lrp, {
          'dialectric_constant': dialectric_constant,
          'conductivity': conductivity, 
          'radio_climate': radio_climate,
          'fraction_of_time':fraction_of_time
          }, '.lrp'),
          (build_splat_az, {}, '.az'),
          (build_splat_el, {}, '.el'),
          ]:
            s = f(t, **kwargs)
            path = out_path/(t['name'] + ext)
            with path.open('w') as tgt:
                tgt.write(s)

def read_transmitters(path):
    """
    INPUTS:

    - ``path``: string or Path object; location of a CSV file of transmitter data

    OUTPUTS:

    Return a list of dictionaries, one for each transmitter in the transmitters
    CSV file.
    The keys for each transmitter come from the header row of the CSV file.
    If ``REQUIRED_TRANSMITTER_FIELDS`` is not a subset of these keys, then
    raise a ``ValueError``
    Additionally, a 'name' field is added to each transmitter dictionary for
    later use and is the result of :func:`build_transmitter_name`.

    NOTES:

    The CSV file of transmitter data should include at least the columns,
    otherwise a ``ValueError`` will be raised.

    - ``'network_name'``: name of transmitter network
    - ``'site_name'``: name of transmitter site
    - ``'longitude'``: WGS84 decimal longitude of transmitter  
    - ``'latitude``: WGS84 decimal latitude of transmitter
    - ``'antenna_height'``: height of transmitter antenna in meters above sea level
    - ``'polarization'``: 0 for horizontal or 1 for vertical
    - ``'frequency'``: frequency of transmitter in MegaHerz
    - ``'power_eirp'``: effective radiated power of transmitter in Watts

    """
    path = Path(path)
    transmitters = []
    with path.open() as src:
        reader = csv.DictReader(src)
        for row in reader:
            transmitters.append(row)
    transmitters = check_and_format_transmitters(transmitters)
    return transmitters

def check_and_format_transmitters(transmitters):
    """
    INPUTS:

    - ``transmitters``: list; same format as output of :func:`read_transmitters`

    OUTPUTS:

    Return the given list of transmitters dictionaries altered as follows.
    For each dictionary, 

    - create a ``name`` field from the ``network_name`` and ``site_name`` fields
    - convert the numerical fields to floats

    Raise a ``ValueError`` if the list of transmitters is empty, or if the 
    ``REQUIRED_TRANSMITTER_FIELDS`` are not present in each transmitter 
    dictionary, or if the any of the field data is improperly formatted.
    """
    if not transmitters:
        raise ValueError('Transmitters must be a nonempty list')

    # Check that required fields are present
    keys = transmitters[0].keys()
    if not set(REQUIRED_TRANSMITTER_FIELDS) <= set(keys):
        raise ValueError('Transmitters header must contain '\
          'at least the fields {!s}'.format(REQUIRED_TRANSMITTER_FIELDS))

    # Format required fields and raise error if run into problems
    new_transmitters = []
    for i, t in enumerate(transmitters):
        try:
            t['name'] = build_transmitter_name(t['network_name'], 
              t['site_name'])
            for key in ['latitude', 'longitude', 'antenna_height', 
                'polarization', 'frequency', 'power_eirp']:
                t[key] = float(t[key])
        except:
            raise ValueError('Data on line {!s} of transmitters file is '\
              'improperly formatted'.format(i + 1))
        new_transmitters.append(t)

    return new_transmitters

def build_transmitter_name(network_name, site_name):
    """
    INPUTS:

    - ``network_name``: string
    - ``site_name``: string

    OUTPUTS:

    Return a string that is the network name with spaces removed followed 
    by an underscore followed by the site name with spaces removed.

    EXAMPLES:

    >>> build_transmitter_name('Slap hAppy', 'Go go go ')
    'SlaphAppy_Gogogo'

    """
    return network_name.replace(' ', '') + '_' +\
      site_name.replace(' ', '')

def build_splat_qth(transmitter):
    """
    INPUTS:

    - ``transmitter``: dictionary of the same form as any one of the elements in the list output by :func:`read_transmitters`

    OUTPUTS:

    Return the text (string) content of a SPLAT! site location file 
    (``.qth`` file) corresponding to the given transmitter.
    """
    t = transmitter
    # Convert to degrees east in range (-360, 0] for SPLAT!
    lon = -t['longitude']
    return "{!s}\n{!s}\n{!s}\n{!s}m".format(
      t['name'], 
      t['latitude'],
      lon, 
      t['antenna_height'])

def build_splat_lrp(transmitter, dialectric_constant=DIALECTRIC_CONSTANT, 
  conductivity=CONDUCTIVITY, radio_climate=RADIO_CLIMATE, 
  fraction_of_time=FRACTION_OF_TIME):
    """
    INPUTS:

    - ``transmitter``: dictionary of the same form as any one of the elements in the list output by :func:`read_transmitters`
    - ``dialectric_constant``: float
    - ``conductivity``: float
    - ``radio_climate``: integer
    - ``fraction_of_time``: float in [0, 1]

    OUTPUTS:

    Return the text (string) content of a SPLAT! irregular topography model
    parameter file (``.lrp`` file) corresponding to the given transmitter.
    """
    t = transmitter
    s = """\
    {!s} ; Earth Dielectric Constant (Relative permittivity)
    {!s} ; Earth Conductivity (Siemens per meter)
    301.000 ; Atmospheric Bending Constant (N-units)
    {!s} ; Frequency in MHz (20 MHz to 20 GHz)
    {!s} ; Radio Climate
    {!s} ; Polarization (0 = Horizontal, 1 = Vertical)
    0.5 ; Fraction of situations
    {!s} ; Fraction of time 
    {!s} ; ERP in watts""".format(
      dialectric_constant, 
      conductivity, 
      t['frequency'],
      radio_climate, 
      t['polarization'], 
      fraction_of_time,
      t['power_eirp'])
    return textwrap.dedent(s)

def build_splat_az(transmitter):
    """
    INPUTS:

    - ``transmitter``: dictionary of the same form as any one of the elements in the list output by :func:`read_transmitters`

    OUTPUTS:

    Return the text (string) content of a SPLAT! azimuth file (``.az`` file)
    corresponding to the given transmitter.

    NOTES:

    A transmitter with no ``'bearing'`` or ``'horizontal_beamwidth'`` data will
    produce the string ``'0  0'``.
    """
    t = transmitter
    try:
        bearing = float(t['bearing'])
        hb = float(t['horizontal_beamwidth'])
        left = int(round(360 - (hb/2)))
        right = int(round(hb/2))
        s = '{!s}\n'.format(bearing)
        for x in range(360):
            if left <= x or x <= right:
                normal = 0.9
            else:
                normal = 0.1
            s += '{!s}  {!s}\n'.format(x, normal)
    except:
        s = '0  0\n'

    return s[:-1] # Drop the final new line 

def build_splat_el(transmitter):
    """
    INPUTS:

    - ``transmitter``: dictionary of the same form as any one of the elements in the list output by :func:`read_transmitters`

    OUTPUTS:

    Return the text (string) content of a SPLAT! elevation file (``.el`` file)
    corresponding to the given transmitter.

    NOTES:

    A transmitter with no ``'bearing'`` or ``'antenna_downtilt'`` or 
    ``'vertical_beamwidth'`` data will produce the string ``'0  0'``.
    """
    t = transmitter
    try:
        bearing = float(t['bearing'])
        ad = float(t['antenna_downtilt'])
        vb = float(t['vertical_beamwidth'])
        s = '{!s}  {!s}\n'.format(ad, bearing)
        counter = 0
        for x in range(-10, 91):
            if counter < vb:
                s += '{!s}  0.9\n'.format(x) 
            else:
                s += '{!s}  0.1\n'.format(x) 
            counter += 1
    except:
        s = '0  0\n'

    return s[:-1]  # Drop the final newline 

def get_lon_lats(transmitters):
    """
    INPUTS:

    - ``transmitters``: a list of transmitters of the form output by :func:`read_transmitters`

    OUTPUTS:

    Return a list of longitude-latitude pairs (float pairs)
    representing the locations of the given transmitters.
    If ``transmitters`` is empty, then return the empty list. 
    """
    return [(t['longitude'], t['latitude']) for t in transmitters]

def create_splat_topography_files(in_path, out_path, high_definition=False):
    """
    INPUTS:

    - ``in_path``: string or Path object specifying a directory
    - ``out_path``: string or Path object specifying a directory
    - ``high_definition``: boolean

    OUTPUTS:

    None.
    Convert each SRTM HGT topography file in the directory ``in_path`` to
    a SPLAT! Data File (SDF) file in the directory ``out_path``, 
    creating the directory if it does not exist.
    If ``high_definition``, then assume the input data is high definition.

    NOTES:

    - Requires and uses SPLAT!'s ``srtm2sdf`` or ``srtm2sdf-hd`` 
      (if ``high_definition``) command to do the conversion
    - Raises a ``subprocess.CalledProcessError`` if SPLAT! fails to 
      convert a file
    """
    in_path = Path(in_path)
    out_path = Path(out_path)
    if not out_path.exists():
        out_path.mkdir(parents=True)

    splat = 'srtm2sdf'
    if high_definition:
        splat += '-hd'

    sdf_pattern = re.compile(r"[\d\w\-\:]+\.sdf")

    for f in in_path.iterdir():
        if not (f.name.endswith('.hgt') or f.name.endswith('.hgt.zip')):
            continue

        # Unzip if necessary
        is_zip = False
        if f.name.endswith('.zip'):
            is_zip = True
            shutil.unpack_archive(str(f), str(f.parent))
            tile_name = f.name.split('.')[0]
            f = f.parent/'{!s}.hgt'.format(tile_name)

        # Convert to SDF
        cp = subprocess.run([splat, f.name], cwd=str(f.parent),
          stdout=subprocess.PIPE, universal_newlines=True, check=True)

        # Get name of output file, which SPLAT! created and which differs
        # from the original name, and move the output to the out path
        m = sdf_pattern.search(cp.stdout)
        name = m.group(0)        
        src = in_path/name
        tgt = out_path/name
        shutil.move(str(src), str(tgt))

        # Clean up
        if is_zip:
            f.unlink()

@ut.time_it
def create_coverage_reports(in_path, out_path, transmitter_names=None,
  receiver_sensitivity=-110, high_definition=False):
    """
    INPUTS:

    - ``in_path``: string or Path object specifying a directory; all the SPLAT! transmitter and elevation data should lie here
    - ``out_path``: string or Path object specifying a directory
    - ``transmitter_names``: list of transmitter names (outputs of :func:`build_transmitter_name`) to restrict to; if ``None``, then all transmitters in ``in_path`` will be used
    - ``receiver_sensitivity``: float; measured in decibels; path loss threshold beyond which signal strength contours will not be plotted
    - ``high_definition``: boolean

    OUTPUTS:

    None. 
    Create a SPLAT! coverage report for every transmitter with data located
    at ``in_path``, or, if ``transmitter_names`` is given, every transmitter 
    in that list with data data located at ``in_path``.
    Write each report to the directory ``out_path``, creating the directory 
    if necessary.
    A report comprises the files

    - ``'<transmitter name>-site_report.txt'``
    - ``'<transmitter name>.kml'``: KML file containing transmitter feature and ``'<transmitter name>.ppm'``
    - ``'<transmitter name>.ppm'``: PPM file depicting a contour plot of the transmitter signal strength
    - ``'<transmitter name>-ck.ppm'``: PPM file depicting a legend for the signal strengths in ``'<transmitter name>.ppm'``

    NOTES:

    On a 2.8 GHz Intel Core i7 processor, this take about 1.15 minutes for 
    one transmitter.
    """
    in_path = Path(in_path)
    out_path = Path(out_path)
    if not out_path.exists():
        out_path.mkdir(parents=True)

    # Get transmitter names
    if transmitter_names is None:
        transmitter_names = [p.stem for p in in_path.iterdir()
          if p.name.endswith('.qth')]

    # Splatify
    splat = 'splat'
    if high_definition:
        splat += '-hd'

    if receiver_sensitivity > 0:
        # SPLAT! prefers negatives
        receiver_sensitivity *= -1

    for t in transmitter_names:
        args = [splat, '-t', t + '.qth', '-L', '8.0', '-dbm', '-db', 
          str(receiver_sensitivity), '-metric', '-ngs', '-kml',
          '-o', t + '.ppm']     
        subprocess.run(args, cwd=str(in_path),
          stdout=subprocess.PIPE, universal_newlines=True, check=True)

    # Move outputs to out_path
    exts = ['.ppm', '-ck.ppm', '-site_report.txt', '.kml']
    for t in transmitter_names:
        for ext in exts:
            src = in_path/(t + ext)
            tgt = out_path/(t + ext) 
            shutil.move(str(src), str(tgt))

def postprocess_coverage_reports(path, delete_ppm=False):
    """
    INPUTS:

    - ``path``: string or Path object; directory where coverage reports (outputs of :func:`create_coverage_reports`) lie
    - ``delete_ppm``: boolean; delete the original, large PPM files in the coverage reports if and only if this flag is ``True``

    OUTPUTS:

    None.
    Using the PPM files in the directory ``path`` do the following:

    - Convert each PPM files into a PNG file, replacing white with transparency using ImageMagick
    - Change the PPM reference in each KML file to the corresponding PNG file
    - Convert the PNG coverage file (not the legend file) into GeoTIFF using GDAL
    """
    # First pass: create PNG from PPM 
    for f in path.iterdir():    
        if f.suffix == '.ppm':
            # Convert to PNG, turning white background into 
            # transparent background
            png = f.stem + '.png'
            args = ['convert', '-transparent', '#FFFFFF', f.name, png]
            subprocess.run(args, cwd=str(path),
              stdout=subprocess.PIPE, universal_newlines=True, check=True)

            # # Resize to width 1200 pixels
            # args = ['convert', '-geometry', '1200', png, png]     
            # subprocess.run(args, cwd=str(path),
            #   stdout=subprocess.PIPE, universal_newlines=True, check=True)

            if delete_ppm:
                # Delete PPM
                f.unlink()

    # Second pass: create KML and convert PNG to GeoTIFF
    for f in path.iterdir():
        if f.suffix == '.kml':
            # Replace PPM with PNG in KML
            with f.open() as src:
                kml = src.read()
            kml = kml.replace('.ppm', '.png')
            with f.open('w') as tgt:
                tgt.write(kml)        

            # Convert main PNG to GeoTIFF using the lon-lat bounds from the KML
            bounds = get_bounds_from_kml(kml)
            epsg = 'EPSG:4326'  # WGS84
            png = f.stem + '.png'
            tif = f.stem + '.tif'
            args = ['gdal_translate', '-of', 'Gtiff', '-a_ullr', 
              str(bounds[0]), str(bounds[3]), str(bounds[2]), str(bounds[1]),
              '-a_srs', epsg, png, tif]
            print(" ".join(args))
            subprocess.run(args, cwd=str(path),
              stdout=subprocess.PIPE, universal_newlines=True, check=True)

def get_bounds_from_kml(kml_string):
    """
    INPUTS:

    - ``kml_string``: string form of a KML file produced by SPLAT!

    OUTPUTS:

    Return a list of floats of the form 
    ``[min_lon, min_lat, max_lon, max_lat]``, describing the WGS84 
    bounding box in the SPLAT! KML coverage file.
    Raise an ``AttributeError`` if the KML does not contain a ``<LatLonBox>``
    entry and hence is not a well-formed SPLAT! KML coverage file.
    """
    kml = kml_string
    west = re.search(r"<west>([0-9-][0-9\.]*)<\/west>", kml).group(1)
    south = re.search(r"<south>([0-9-][0-9\.]*)<\/south>", kml).group(1)
    east = re.search(r"<east>([0-9-][0-9\.]*)<\/east>", kml).group(1)
    north = re.search(r"<north>([0-9-][0-9\.]*)<\/north>", kml).group(1)
    result = [west, south, east, north]
    return list(map(float, result))
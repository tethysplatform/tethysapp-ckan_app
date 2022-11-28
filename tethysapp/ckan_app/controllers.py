import os
import urllib
import tarfile
import netCDF4 as nc
import datetime

from django.shortcuts import render, redirect
from django.core.urlresolvers import reverse

from tethys_apps.sdk import get_dataset_engine
from tethys_apps.sdk.gizmos import *


def home(request):
    """
    Controller for the app home page.
    """
    # Get an engine object to work with CKAN
    ckan_engine = get_dataset_engine(name="nfie")

    # Get a list of datasets
    response = ckan_engine.list_datasets()

    # Assemble a list of ERFP datasets
    erfp_dataset_names = []

    if response['success']:
        for dataset_name in response['result']:
            if 'erfp' in dataset_name:
                erfp_dataset_names.append(dataset_name)

    # Assemble a list of unique watersheds
    unique_watersheds = []

    for erfp_dataset_name in erfp_dataset_names:
        parts = erfp_dataset_name.split('-')
        no_time = '-'.join(parts[:3])
        
        if no_time not in unique_watersheds:
            unique_watersheds.append(no_time)
    
    # Assemble the list of options for the watershed select input
    watershed_options = []

    for watershed in unique_watersheds:
        parts = watershed.split('-')
        pretty_watershed_name = parts[1].replace('_', ' ').title()
        pretty_subbasin_name = parts[2].replace('_', ' ').title()
        combined = pretty_watershed_name + ', ' + pretty_subbasin_name

        watershed_options.append((combined, watershed))

    # Define the watershed select input
    select_options = SelectInput(display_text='Watershed',
                                 name='watershed',
                                 multiple=False,
                                 options=watershed_options)

    # Assemble options for the time select input
    time_options = []
    show_time = False
    selected_watershed = ''

    # Handle form submission with the watershed select input
    if request.POST and 'watershed' in request.POST:
        selected_watershed = request.POST['watershed']
        show_time = True

        for dataset_name in erfp_dataset_names:
            if selected_watershed in dataset_name:
                parts = dataset_name.split('-')
                time = parts[-1]
                year = time[:4]
                month = time[4:6]
                day = time[6:8]
                hour = time[9:11]
                pretty_time = '{0}/{1}/{2} @ {3}'.format(month, day, year, hour)
                time_options.append((pretty_time, dataset_name))

    # Define time select input
    time_select_options = SelectInput(display_text='Time',
                                      name='time',
                                      multiple=False,
                                      options=time_options)

        # Handle form submission with the time select input
    if request.POST and 'time' in request.POST:
        selected_dataset = request.POST['time']
        return redirect('ckan_app:forecasts', watershed_dataset=selected_dataset)

    context = {'unique_watersheds': unique_watersheds,
               'select_options': select_options,
               'time_select_options': time_select_options,
               'show_time': show_time,
               'selected_watershed': selected_watershed}

    return render(request, 'ckan_app/home.html', context)

def forecasts(request, watershed_dataset):
    """
    Controller for forecasts
    """
    # Create more user friendly names from the watershed_dataset variable
    parts = watershed_dataset.split('-')
    pretty_watershed_name = parts[1].replace('_', ' ').title()
    pretty_subbasin_name = parts[2].replace('_', ' ').title()
    title = pretty_watershed_name + ', ' + pretty_subbasin_name

    # User friendly time
    time = parts[-1]
    year = time[:4]
    month = time[4:6]
    day = time[6:8]
    hour = time[9:11]
    pretty_time = '{0}/{1}/{2} @ {3}'.format(month, day, year, hour)

    # Get a CKAN engine
    ckan_engine = get_dataset_engine(name='nfie')

    # Retrieve the dataset
    response = ckan_engine.get_dataset(dataset_id=watershed_dataset)

    # Assemble a list of buttons
    buttons = []

    if response['success']:
        dataset = response['result']
        
        for resource in dataset['resources']:
            plot_url = reverse('ckan_app:plot', args=[resource['id']])
            button = Button(display_text=resource['name'],
                            href=plot_url)
            buttons.append(button)

    context = {'title': title,
               'pretty_time': pretty_time,
               'buttons': buttons}

    return render(request, 'ckan_app/forecasts.html', context)

def plot(request, resource_id):
    """
    Controller for forecast plots
    """
    ckan_engine = get_dataset_engine(name='nfie')

    response = ckan_engine.get_resource(resource_id=resource_id)

    title = 'No Forecast Found'
    pretty_time = ''
    forecast_number = ''
    timeseries = []

    if response['success']:
        resource = response['result']

        # Get pretty watershed name
        resource_name = resource['name']
        parts = resource_name.split('-')
        pretty_watershed_name = parts[1].replace('_', ' ').title()
        pretty_subbasin_name = parts[2].replace('_', ' ').title()
        title = pretty_watershed_name + ', ' + pretty_subbasin_name

        # Get pretty time
        time = parts[-2]
        year = time[:4]
        month = time[4:6]
        day = time[6:8]
        hour = time[9:11]
        pretty_time = '{0}/{1}/{2} @ {3}'.format(month, day, year, hour)

        # Get the forecast number
        forecast_number = parts[-1]

        # Create a workspace directory for the current user
        current_username = request.user.username
        controllers_directory = os.path.dirname(__file__)
        user_workspace = os.path.join(controllers_directory, 'workspace', current_username)

        if not os.path.exists(user_workspace):
            os.makedirs(user_workspace)

        # Clean out the workspace directory for the current user
        for filename in os.listdir(user_workspace):
            os.remove(os.path.join(user_workspace, filename))

        # Download the resource into the current user workspace
        file_name = os.path.join(user_workspace, 'temp.gz')
        urllib.urlretrieve(resource['url'], file_name)

        # Extract the archive file
        with tarfile.open(file_name) as tar:
            def is_within_directory(directory, target):
                
                abs_directory = os.path.abspath(directory)
                abs_target = os.path.abspath(target)
            
                prefix = os.path.commonprefix([abs_directory, abs_target])
                
                return prefix == abs_directory
            
            def safe_extract(tar, path=".", members=None, *, numeric_owner=False):
            
                for member in tar.getmembers():
                    member_path = os.path.join(path, member.name)
                    if not is_within_directory(path, member_path):
                        raise Exception("Attempted Path Traversal in Tar File")
            
                tar.extractall(path, members, numeric_owner=numeric_owner) 
                
            
            safe_extract(tar, user_workspace)
        
        # Search directory for files with the netCDF extension (.nc)
        netcdf_file_path = ''
        
        for filename in os.listdir(user_workspace):
            if '.nc' in filename:
                netcdf_file_path = os.path.join(user_workspace, filename)

                # Break the loop after the first one is found 
                # (hopefully, the directory has been cleared, 
                # so there should only be one)
                break
        
        # Open the netCDF file
        data_nc = nc.Dataset(netcdf_file_path, mode="r")
        
        # Arbitrary reach id
        reach_index = 0

        # Check the order of the time and comid fields and get the data vaules
        qout_dimensions = data_nc.variables['Qout'].dimensions

        if qout_dimensions[0].lower() == 'time' and qout_dimensions[1].lower() == 'comid':
            data_values = data_nc.variables['Qout'][:,reach_index]
        elif qout_dimensions[0].lower() == 'comid' and qout_dimensions[1].lower() == 'time':
            data_values = data_nc.variables['Qout'][reach_index,:]

        # Assemble the time stamps for each value given 
        # the starting date and a 6 hour timestep
        start_date = datetime.datetime(int(year), int(month), int(day), int(hour))
        timeseries = []
        step = 0

        for data_value in data_values.tolist():
            hours = 6 * step
            time = start_date + datetime.timedelta(hours=hours)
            timeseries.append([time, data_value])
            step += 1

        # Close the netCDF file
        data_nc.close()
                

    # Define the time series plot
    time_series_plot_object = HighChartsTimeSeries(
                                title='Streamflow Forecast',
                                y_axis_title='Streamflow',
                                y_axis_units='cms',
                                series=[{
                                            'name': 'Streamflow',
                                            'data': timeseries
                                        }]
    )

    # Define the plot view
    time_series_plot = PlotView(highcharts_object=time_series_plot_object,
                                width='100%',
                                height='500px')

    context = {'title': title,
               'pretty_time': pretty_time,
               'forecast_number': forecast_number,
               'time_series_plot': time_series_plot}

    return render(request, 'ckan_app/plot.html', context)
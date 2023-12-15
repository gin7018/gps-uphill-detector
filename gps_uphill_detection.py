import math
from datetime import datetime

import pynmea2
import simplekml
import sys


class GPSREC:
    def __init__(self, timestamp, longitude, latitude, altitude, uphill=False):
        self.timestamp = timestamp
        self.longitude = longitude
        self.latitude = latitude
        self.altitude = altitude
        self.uphill = uphill


def kml_generator(uphill_detected):
    """
    Given a list of all coordinates that have the uphill flag on or off, generates
    a KML file which draws the trajectory path and shows uphill movement with red
    and normal movement with green
    :param uphill_detected a list of all coordinates that have the uphill flag on or off
    :return None
    """
    kml = simplekml.Kml(name="Up Hill Detector")

    def reformat(coord):
        return float(coord.longitude), float(coord.latitude), coord.altitude

    for i in range(len(uphill_detected)):
        if i + 1 >= len(uphill_detected):
            break

        point = reformat(uphill_detected[i])
        next_point = reformat(uphill_detected[i + 1])

        ls = kml.newlinestring()
        ls.coords = [point, next_point]
        if uphill_detected[i].uphill:
            ls.style.linestyle.color = simplekml.Color.red
        else:
            ls.style.linestyle.color = simplekml.Color.lightgreen
        ls.style.linestyle.width = 6

    kml.save("result.kml")


def read_gpgga(filename):
    """
    reads gps data of GPGGA format to retrieve the longitude, latitude and altitude
    coordinates
    :param filename the file name of the gps data
    :return a list of all the coordinates
    """
    gga_data = []
    with open(filename) as gpsf:
        for line in gpsf:
            if line.startswith("$GPGGA"):
                try:
                    gga_sentence = pynmea2.parse(line.strip())
                    record = GPSREC(gga_sentence.timestamp, gga_sentence.longitude, gga_sentence.latitude,
                                    gga_sentence.altitude)
                    gga_data.append(record)
                except pynmea2.ParseError:
                    print("error parsing")
                    continue
    return gga_data


def clean_gga_data(data):
    """"
    you do not need multiple data points at that same location
    data should contain unique lats and longs
    filter by longs and lats
    :param data the gps data to be cleaned
    :return gps data with unique longitude and latitude coordinates
    """

    coordinates = {}
    minimum_elapsed_time = 120  # in seconds
    for coord in data:
        if (coord.longitude, coord.latitude) not in coordinates:
            coordinates[(coord.longitude, coord.latitude)] = coord
        else:
            record = coordinates[(coord.longitude, coord.latitude)]

            d1 = datetime.combine(datetime.today(), record.timestamp)
            d2 = datetime.combine(datetime.today(), coord.timestamp)
            elapsed_time = abs(d1 - d2)

            if elapsed_time.total_seconds() > minimum_elapsed_time:
                coordinates[(coord.longitude, coord.latitude)] = coord

    return coordinates.values()


def get_distance_between_locations(point1, point2):
    """
    Calculate the great circle distance in kilometers between two points
    on the earth (specified in decimal degrees)
    :param point1: the first lat and long coordinates
    :param point2: the second coordinate
    :return the distance between point1 and point2 in kilometers
    """
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [point1.latitude, point1.longitude, point2.latitude, point2.longitude])

    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    # Radius of Earth in kilometers is 6371
    km_earth_radius = 6371.0
    distance = km_earth_radius * c

    return distance


def detect_uphill(data):
    """
    Given location data points, detects uphill movement by:
        first sorting by timestamp
        going from point to points and checking if the change in altitude is >= 0.3
    :param data: the location data points
    :return: a list of data points that are either going uphill or not
    """

    def sort_by_timestamp(record):
        return record.timestamp

    detecting_uphill_data = sorted(data, key=sort_by_timestamp)
    point_to_point_elevation_threshold = 0.3
    for i in range(len(data)):
        if i + 1 < len(data):
            going_uphill = ((detecting_uphill_data[i + 1].altitude - detecting_uphill_data[i].altitude)
                            >= point_to_point_elevation_threshold)
            if going_uphill:
                detecting_uphill_data[i].uphill = True

    # the government mileage rate is $0.52 per mile
    # so if a car is travelling more than 1/2 a mile uphill this counts as
    # a significant uphill movements

    # identify elevation segments, check how long they are in distance
    # compare to threshold and turn off the uphill flag for segments that
    # are not long enough
    significant_distance_of_elevation_threshold = 10.0  # in meters
    segment = []
    for i in range(len(detecting_uphill_data)):
        if detecting_uphill_data[i].uphill:
            segment.append(detecting_uphill_data[i])
        else:
            if len(segment) == 0:
                continue

            sorted(segment, key=sort_by_timestamp)
            start_location = segment[0]
            end_location = segment[-1]
            distance = get_distance_between_locations(start_location, end_location) * 1000  # convert to meters

            if distance < significant_distance_of_elevation_threshold:
                for point in segment:
                    point.uphill = False

            segment = []
    return detecting_uphill_data


def main():
    if len(sys.argv) != 2:
        print("No GPS file name provided")
        return

    gps_data_by_day = sys.argv[1]
    data = read_gpgga(gps_data_by_day)

    unique_gps_data = clean_gga_data(data)
    uphill_detected = detect_uphill(unique_gps_data)

    kml_generator(uphill_detected)
    print("kml file generated")


if __name__ == '__main__':
    main()

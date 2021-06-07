# (C) Copyright 2019-2021 Hewlett Packard Enterprise Development LP.
# Apache License 2.0

from pyaoscx.exceptions.response_error import ResponseError
from pyaoscx.exceptions.generic_op_error import GenericOperationError
from pyaoscx.exceptions.verification_error import VerificationError

from pyaoscx.pyaoscx_module import PyaoscxModule
from pyaoscx.utils.connection import connected

import json
import logging
import re
import pyaoscx.utils.util as utils


class BgpNeighbor(PyaoscxModule):
    '''
    Provide configuration management for BGP Neighbor on AOS-CX devices.
    '''

    indices = ['ip_or_ifname_or_group_name']
    resource_uri_name = 'bgp_neighbors'

    def __init__(self, session, ip_or_ifname_or_group_name, parent_bgp_router,
                 uri=None, **kwargs):

        self.session = session
        # Assign ID
        self.ip_or_ifname_or_group_name = ip_or_ifname_or_group_name
        # Assign parent BGP Router
        self.__set_bgp_router(parent_bgp_router)
        self._uri = uri
        # List used to determine attributes related to the BGP configuration
        self.config_attrs = []
        self.materialized = False
        # Attribute dictionary used to manage the original data
        # obtained from the GET
        self.__original_attributes = {}
        # Set arguments needed for correct creation
        utils.set_creation_attrs(self, **kwargs)
        # Attribute used to know if object was changed recently
        self.__modified = False

    def __set_bgp_router(self, parent_bgp_router):
        '''
        Set parent BgpRouter object as an attribute for the BGP class
        :param parent_bgp_router a BgpRouter object
        '''

        # Set parent BGP Router
        self.__parent_bgp_router = parent_bgp_router

        # Set URI
        self.base_uri = \
            '{base_bgp_router_uri}/{bgp_router_asn}/bgp_neighbors'.format(
                base_bgp_router_uri=self.__parent_bgp_router.base_uri,
                bgp_router_asn=self.__parent_bgp_router.asn)

        for bgp_ngh in self.__parent_bgp_router.bgp_neighbors:
            if bgp_ngh.ip_or_ifname_or_group_name \
                    == self.ip_or_ifname_or_group_name:
                # Make list element point to current object
                bgp_ngh = self
            else:
                # Add self to BGP Neighbors list in parent BGP Router
                self.__parent_bgp_router.bgp_neighbors.append(self)

    @connected
    def get(self, depth=None, selector=None):
        '''
        Perform a GET call to retrieve data for a BGP Neighbor table entry and fill
        the object with the incoming attributes

        :param depth: Integer deciding how many levels into the API JSON that
            references will be returned.
        :param selector: Alphanumeric option to select specific information to
            return.
        :return: Returns True if there is not an exception raised
        '''
        logging.info("Retrieving the switch BGP Neighbors")

        depth = self.session.api_version.default_depth\
            if depth is None else depth
        selector = self.session.api_version.default_selector\
            if selector is None else selector

        if not self.session.api_version.valid_depth(depth):
            depths = self.session.api_version.valid_depths
            raise Exception("ERROR: Depth should be {}".format(depths))

        if selector not in self.session.api_version.valid_selectors:
            selectors = ' '.join(self.session.api_version.valid_selectors)
            raise Exception(
                "ERROR: Selector should be one of {}".format(selectors))

        payload = {
            "depth": depth,
            "selector": selector
        }

        uri = "{base_url}{class_uri}/{id}".format(
            base_url=self.session.base_url,
            class_uri=self.base_uri,
            id=self.ip_or_ifname_or_group_name
        )

        try:
            response = self.session.s.get(
                uri, verify=False, params=payload, proxies=self.session.proxy)

        except Exception as e:
            raise ResponseError('GET', e)

        if not utils._response_ok(response, "GET"):
            raise GenericOperationError(response.text, response.status_code)

        data = json.loads(response.text)

        # Add dictionary as attributes for the object
        utils.create_attrs(self, data)

        # Determines if the BGP Neighbor is configurable
        if selector in self.session.api_version.configurable_selectors:
            # Set self.config_attrs and delete ID from it
            utils.set_config_attrs(
                self, data, 'config_attrs', ['ip_or_ifname_or_group_name'])

        # Set original attributes
        self.__original_attributes = data
        # Remove ID
        if 'ip_or_ifname_or_group_name' in self.__original_attributes:
            self.__original_attributes.pop('ip_or_ifname_or_group_name')

        # If the BGP Neighbor has a local_interface inside the switch
        if hasattr(self, 'local_interface') and \
                self.local_interface is not None:
            local_interface_response = self.local_interface
            interface_cls = self.session.api_version.get_module(
                self.session, 'Interface', '')
            # Set port as a Interface Object
            self.local_interface = interface_cls.from_response(
                self.session, local_interface_response)
            self.local_interface.get()

        # Sets object as materialized
        # Information is loaded from the Device
        self.materialized = True
        return True

    @classmethod
    def get_all(cls, session, parent_bgp_router):
        '''
        Perform a GET call to retrieve all system BGP Neighbors inside a BGP
        Router, and create a dictionary containing them
        :param cls: Object's class
        :param session: pyaoscx.Session object used to represent a logical
            connection to the device
        :param parent_bgp_router: parent BgpRouter object where BGP Neighbor is stored
        :return: Dictionary containing BGP Neighbors IDs as keys and a BGP
            Neighbors objects as values
        '''

        logging.info("Retrieving the switch BGP Neighbors")

        base_uri = \
            '{base_bgp_router_uri}/{bgp_router_asn}/bgp_neighbors'.format(
                base_bgp_router_uri=parent_bgp_router.base_uri,
                bgp_router_asn=parent_bgp_router.asn)

        uri = '{base_url}{class_uri}'.format(
            base_url=session.base_url,
            class_uri=base_uri)

        try:
            response = session.s.get(uri, verify=False, proxies=session.proxy)
        except Exception as e:
            raise ResponseError('GET', e)

        if not utils._response_ok(response, "GET"):
            raise GenericOperationError(response.text, response.status_code)

        data = json.loads(response.text)

        bgp_dict = {}
        # Get all URI elements in the form of a list
        uri_list = session.api_version.get_uri_from_data(data)

        for uri in uri_list:
            # Create a BgpNeighbor object
            ip_or_ifname_or_group_name, bgp_neighbor = BgpNeighbor.from_uri(
                session, parent_bgp_router, uri)
            # Load all BGP Neighbor data from within the Switch
            bgp_neighbor.get()
            bgp_dict[ip_or_ifname_or_group_name] = bgp_neighbor

        return bgp_dict

    @connected
    def apply(self):
        '''
        Main method used to either create or update an existing
        BGP Neighbor table entry.
        Checks whether the BGP Neighbor exists in the switch
        Calls self.update() if BGP Neighbor is being updated
        Calls self.create() if a new BGP Neighbor is being created

        :return modified: Boolean, True if object was created or modified
            False otherwise

        '''
        if not self.__parent_bgp_router.materialized:
            self.__parent_bgp_router.apply()

        modified = False
        if self.materialized:
            modified = self.update()
        else:
            modified = self.create()
        # Set internal attribute
        self.__modified = modified
        return modified

    @connected
    def update(self):
        '''
        Perform a PUT call to apply changes to an existing  BGP Neighbor table entry

        :return modified: True if Object was modified and a PUT request was made.
            False otherwise

        '''
        # Variable returned
        modified = False

        bgp_neighbor_data = {}

        bgp_neighbor_data = utils.get_attrs(self, self.config_attrs)

        # Get ISL port uri
        if self.local_interface is not None:
            bgp_neighbor_data["local_interface"] = \
                self.local_interface.get_info_format()

        uri = "{base_url}{class_uri}/{id}".format(
            base_url=self.session.base_url,
            class_uri=self.base_uri,
            id=self.ip_or_ifname_or_group_name
        )

        # Compare dictionaries
        if bgp_neighbor_data == self.__original_attributes:
            # Object was not modified
            modified = False

        else:
            put_data = json.dumps(bgp_neighbor_data, sort_keys=True, indent=4)

            try:
                response = self.session.s.put(
                    uri, verify=False, data=put_data, proxies=self.session.proxy)

            except Exception as e:
                raise ResponseError('PUT', e)

            if not utils._response_ok(response, "PUT"):
                raise GenericOperationError(
                    response.text, response.status_code)

            else:
                logging.info(
                    "SUCCESS: Update BGP table entry {} succeeded".format(
                        self.ip_or_ifname_or_group_name))
            # Set new original attributes
            self.__original_attributes = bgp_neighbor_data
            # Object was modified
            modified = True
        return modified

    @connected
    def create(self):
        '''
        Perform a POST call to create a new BGP Neighbor table entry
        Only returns if an exception is not raise

        :return modified: Boolean, True if entry was created

        '''

        bgp_neighbor_data = {}

        bgp_neighbor_data = utils.get_attrs(self, self.config_attrs)
        bgp_neighbor_data['ip_or_ifname_or_group_name'] = \
            self.ip_or_ifname_or_group_name

        if hasattr(self, 'local_interface'):

            # If local interface is NOT a string
            if not isinstance(self.local_interface, str):
                if not self.local_interface.materialized:
                    raise VerificationError(
                        'Local Interface',
                        'Object not materialized')

                # Get ISL port uri
                bgp_neighbor_data["local_interface"] = \
                    self.local_interface.get_info_format()

        uri = "{base_url}{class_uri}".format(
            base_url=self.session.base_url,
            class_uri=self.base_uri
        )
        post_data = json.dumps(bgp_neighbor_data, sort_keys=True, indent=4)

        try:
            response = self.session.s.post(
                uri, verify=False, data=post_data, proxies=self.session.proxy)

        except Exception as e:
            raise ResponseError('POST', e)

        if not utils._response_ok(response, "POST"):
            raise GenericOperationError(response.text, response.status_code)

        else:
            logging.info("SUCCESS: Adding BGP table entry {} succeeded".format(
                self.ip_or_ifname_or_group_name))

        # Get all object's data
        self.get()

        # Object was modified, as it was created inside Device
        return True

    @connected
    def delete(self):
        '''
        Perform DELETE call to delete  BGP Neighbor table entry.

        '''

        uri = "{base_url}{class_uri}/{id}".format(
            base_url=self.session.base_url,
            class_uri=self.base_uri,
            id=self.ip_or_ifname_or_group_name
        )

        try:
            response = self.session.s.delete(
                uri, verify=False, proxies=self.session.proxy)

        except Exception as e:
            raise ResponseError('DELETE', e)

        if not utils._response_ok(response, "DELETE"):
            raise GenericOperationError(response.text, response.status_code)

        else:
            logging.info("SUCCESS: Delete BGP table entry {} succeeded".format(
                self.ip_or_ifname_or_group_name))

        # Delete back reference from BGP_Routers
        for neighbor in self.__parent_bgp_router.bgp_neighbors:
            if neighbor.ip_or_ifname_or_group_name == \
                    self.ip_or_ifname_or_group_name:
                self.__parent_bgp_router.bgp_neighbors.remove(neighbor)

        # Delete object attributes
        utils.delete_attrs(self, self.config_attrs)

    @classmethod
    def from_response(cls, session, parent_bgp_router, response_data):
        '''
        Create a  BgpNeighbor object given a response_data related to the BGP Router
        ID object
        :param cls: Object's class
        :param session: pyaoscx.Session object used to represent a logical
            connection to the device
        :param parent_bgp_router: parent BgpRouter object where BGP Neighbor is stored
        :param response_data: The response can be either a
            dictionary: {
                    id: "/rest/v10.04/system/vrfs/<vrf_name>/bgp_routers/asn
                        /bgp_neighbors/id"
                }
            or a
            string: "/rest/v10.04/system/vrfs/<vrf_name>/bgp_routers/asn/
                bgp_neighbors/id"
        :return: BgpNeighbor object
        '''
        bgp_arr = session.api_version.get_keys(
            response_data, BgpNeighbor.resource_uri_name)
        bgp_neighbor_id = bgp_arr[0]
        return BgpNeighbor(session, bgp_neighbor_id, parent_bgp_router)

    @classmethod
    def from_uri(cls, session, parent_bgp_router, uri):
        '''
        Create a BgpNeighbor object given a URI
        :param cls: Object's class
        :param session: pyaoscx.Session object used to represent a logical
            connection to the device
        :param parent_bgp_router: parent BgpRouter object where BGP Neighbor is stored
        :param uri: a String with a URI

        :return index, bgp_obj: tuple containing both the BGP object and the
            BGP's ID
        '''
        # Obtain ID from URI
        index_pattern = re.compile(r'(.*)bgp_neighbors/(?P<index>.+)')
        index = index_pattern.match(uri).group('index')

        # Create BGP object
        bgp_obj = BgpNeighbor(
            session, index, parent_bgp_router, uri=uri)

        return index, bgp_obj

    def __str__(self):
        return "Bgp Neighbor ID {}".format(
            self.ip_or_ifname_or_group_name)

    def get_uri(self):
        '''
        Method used to obtain the specific BGP Neighbor URI
        return: Object's URI
        '''
        if self._uri is None:
            self._uri = '{resource_prefix}{class_uri}/{id}'.format(
                resource_prefix=self.session.resource_prefix,
                class_uri=self.base_uri,
                id=self.ip_or_ifname_or_group_name
            )

        return self._uri

    def get_info_format(self):
        '''
        Method used to obtain correct object format for referencing inside
        other objects
        return: Object format depending on the API Version
        '''
        return self.session.api_version.get_index(self)

    def was_modified(self):
        """
        Getter method for the __modified attribute
        :return: Boolean True if the object was recently modified, False otherwise.
        """

        return self.__modified
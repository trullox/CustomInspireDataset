# encoding: utf-8
import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit




class CustominspiredatasetPlugin(plugins.SingletonPlugin, toolkit.DefaultDatasetForm):
    plugins.implements(plugins.IConfigurer)
    plugins.implements(plugins.IRoutes, inherit=True)
    plugins.implements(plugins.IDatasetForm)
    

    
     # IConfigurer
    def update_config(self, config_):
        toolkit.add_template_directory(config_, 'templates')
        toolkit.add_public_directory(config_, 'public')
        toolkit.add_resource('fanstatic', 'CustomInspireDataset')
        
        
    # IRoutes
    def before_map(self, map):
        cid_package_controller = 'ckanext.CustomInspireDataset.controllers.cidpackagecontroller:CidPackage'
        map.connect('/dataset/new_resource/{id}',
                    controller = cid_package_controller, action='new_resource')
        map.connect('/dataset/{id}/resource_edit/{resource_id}',
                    controller = cid_package_controller, action='resource_edit')
        return map
    
    def after_map(self, map):
        return map
    

    
    def is_fallback(self):
        # Return True to register this plugin as the default handler for
        # package types not handled by any other IDatasetForm plugin.
        return True

    def package_types(self):
        # This plugin doesn't handle any special package types, it just
        # registers itself as the default (above).
        return ('dataset',)
        #return []    
        
 
        
   
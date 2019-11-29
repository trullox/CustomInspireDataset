from ckan.lib.base import model, abort, response, h, BaseController
from ckan.plugins.toolkit import c, request, get_action, check_access, h, render, ObjectNotFound, NotAuthorized, StopOnError, ValidationError
from ckan.controllers.package import PackageController
from ckan.logic import NotFound, clean_dict, tuplize_dict, parse_params
import ckan.lib.navl.dictization_functions as dict_fns
from urllib import urlencode, urlretrieve
import datetime
import mimetypes
import cgi
import os
import requests
import urllib2
import httplib
from ckan.common import json, _, config


class CidPackage(PackageController):

   



    def _resource_form(self, package_type=None):
        return 'package/cid_resource_form.html'



    def __before__(self, action, **params):
        super(PackageController, self).__before__(action, **params)
        c.all_resources = 'all' in request.params.keys()
        c.euosme = config.get('ckan.CustomInspireDataset.euosme.url', "")
        
       
        
            
        
    def _save_new(self, context, package_type=None):
        # The staged add dataset used the new functionality when the dataset is
        # partially created so we need to know if we actually are updating or
        # this is a real new.
        is_an_update = False
        
        ckan_phase = request.params.get('_ckan_phase')
        from ckan.lib.search import SearchIndexError
        try:
            data_dict = clean_dict(dict_fns.unflatten(
                tuplize_dict(parse_params(request.POST))))
            if ckan_phase:
                # prevent clearing of groups etc
                context['allow_partial_update'] = True
                # sort the tags
                if 'tag_string' in data_dict:
                    data_dict['tags'] = self._tag_string_to_list(
                        data_dict['tag_string'])
                if data_dict.get('pkg_name'):
                    is_an_update = True
                    # This is actually an update not a save
                    data_dict['id'] = data_dict['pkg_name']
                    del data_dict['pkg_name']
                    # don't change the dataset state
                    data_dict['state'] = 'draft'
                    # this is actually an edit not a save
                    pkg_dict = get_action('package_update')(context, data_dict)

                    if request.params['save'] == 'go-metadata':
                        # redirect to add metadata
                        url = h.url_for(controller='package',
                                        action='new_metadata',
                                        id=pkg_dict['name'])
                    else:
                        # redirect to add dataset resources
                        url = h.url_for(controller='package',
                                        action='new_resource',
                                        id=pkg_dict['name'])
                    h.redirect_to(url)
                # Make sure we don't index this dataset
                if request.params['save'] not in ['go-resource',
                                                  'go-metadata']:
                    data_dict['state'] = 'draft'
                # allow the state to be changed
                context['allow_state_change'] = True

            data_dict['type'] = package_type
            context['message'] = data_dict.get('log_message', '')
            pkg_dict = get_action('package_create')(context, data_dict)             
          
            if ckan_phase:                
                url = h.url_for(controller='package',
                                action='new_resource',
                                id=pkg_dict['name'])
                h.redirect_to(url)

            self._form_save_redirect(pkg_dict['name'], 'new',
                                     package_type=package_type)
        except NotAuthorized:
            abort(403, _('Unauthorized to read package %s') % '')
        except NotFound, e:
            abort(404, _('Dataset not found'))
        except dict_fns.DataError:
            abort(400, _(u'Integrity Error'))
        except SearchIndexError, e:
            try:
                exc_str = unicode(repr(e.args))
            except Exception:  # We don't like bare excepts
                exc_str = unicode(str(e))
            abort(500, _(u'Unable to add package to search index.') + exc_str)
        except ValidationError, e:
            errors = e.error_dict
            error_summary = e.error_summary
            if is_an_update:
                # we need to get the state of the dataset to show the stage we
                # are on.
                pkg_dict = get_action('package_show')(context, data_dict)
                data_dict['state'] = pkg_dict['state']
                return self.edit(data_dict['id'], data_dict,
                                 errors, error_summary)
            data_dict['state'] = 'none'
            return self.new(data_dict, errors, error_summary)
        
    def new_resource(self, id, data=None, errors=None, error_summary=None):
        ''' FIXME: This is a temporary action to allow styling of the
        forms. '''

        euosme_path = config.get('ckan.CustomInspireDataset.euosme.path', "")
        ckan_url = config.get('ckan.site_url')     
        if request.method == 'POST' and not data:
            save_action = request.params.get('save')
            data = data or \
                clean_dict(dict_fns.unflatten(tuplize_dict(parse_params(
                                                           request.POST))))
            # we don't want to include save as it is part of the form
            del data['save']
            resource_id = data['id']
            del data['id']

            context = {'model': model, 'session': model.Session,
                       'user': c.user, 'auth_user_obj': c.userobj}

            # see if we have any data that we are trying to save
            data_provided = False
            for key, value in data.iteritems():
                if ((value or isinstance(value, cgi.FieldStorage))
                        and key != 'resource_type'):
                    data_provided = True
                    break          
            if not data_provided and save_action != "go-dataset-complete":
                if save_action == 'go-dataset':
                    # go to final stage of adddataset
                    h.redirect_to(controller='package', action='edit', id=id)
                # see if we have added any resources
                try:                 
                    data_dict = get_action('package_show')(context, {'id': id})
                except NotAuthorized:
                    abort(403, _('Unauthorized to update dataset'))
                except NotFound:
                    abort(404, _('The dataset {id} could not be found.'
                                 ).format(id=id))
                if not len(data_dict['resources']):
                    # no data so keep on page
                    msg = _('You must add at least one data resource')
                    # On new templates do not use flash message

                    if asbool(config.get('ckan.legacy_templates')):
                        h.flash_error(msg)
                        h.redirect_to(controller='package',
                                      action='new_resource', id=id)
                    else:
                        errors = {}
                        error_summary = {_('Error'): msg}
                        return self.new_resource(id, data, errors,
                                                 error_summary)
                # XXX race condition if another user edits/deletes
                data_dict = get_action('package_show')(context, {'id': id})
                get_action('package_update')(
                    dict(context, allow_state_change=True),
                    dict(data_dict, state='active'))
                h.redirect_to(controller='package', action='read', id=id)
            data['package_id'] = id
            try:
                if resource_id:
                    data['id'] = resource_id
                    get_action('resource_update')(context, data)
                else:
                    if(request.params.get('format')=='INSPIRE'):
                        home_dir = os.path.join(euosme_path)                       
                        random=request.POST['inspire_random_name'];
                        inspire_file_name = ""
                        if(data["name"]):
                            inspire_file_name = str(data["name"])                           
                        else:
                            inspire_file_name = random                                              
                        filelocation=home_dir+'/'+random+'.xml'
                        api = c.userobj.apikey
                        descr = request.params.get('description')
                        if(descr):
                            descr = str(descr)
                        else:
                            descr = ""
                        r = requests.post(ckan_url+'/api/action/resource_create',
                                  data={'package_id': id,
                                  'name': inspire_file_name,
                                  'format': 'INSPIRE',
                                  'description': descr,
                                  'url': 'upload',  # Needed to pass validation
                                  },                                
                                  headers={'Authorization': api},#api_key},
                                  files=[('upload', file(filelocation))])
                    else:                                  
                        get_action('resource_create')(context, data)
                    #get_action('resource_create')(context, data)
            except ValidationError, e:
                errors = e.error_dict
                error_summary = e.error_summary
                return self.new_resource(id, data, errors, error_summary)
            except NotAuthorized:
                abort(403, _('Unauthorized to create a resource'))
            except NotFound:
                abort(404, _('The dataset {id} could not be found.'
                             ).format(id=id))
            if save_action == 'go-metadata':
                # XXX race condition if another user edits/deletes
                data_dict = get_action('package_show')(context, {'id': id})
                get_action('package_update')(
                    dict(context, allow_state_change=True),
                    dict(data_dict, state='active'))
                h.redirect_to(controller='package', action='read', id=id)
            elif save_action == 'go-dataset':
                # go to first stage of add dataset
                h.redirect_to(controller='package', action='edit', id=id)
            elif save_action == 'go-dataset-complete':
                # go to first stage of add dataset
                h.redirect_to(controller='package', action='read', id=id)
            else:
                # add more resources
                h.redirect_to(controller='package', action='new_resource',
                              id=id)

        # get resources for sidebar
        context = {'model': model, 'session': model.Session,
                   'user': c.user, 'auth_user_obj': c.userobj}
        try:
            pkg_dict = get_action('package_show')(context, {'id': id})
        except NotFound:
            abort(404, _('The dataset {id} could not be found.').format(id=id))
        try:
            check_access(
                'resource_create', context, {"package_id": pkg_dict["id"]})
        except NotAuthorized:
            abort(403, _('Unauthorized to create a resource for this package'))

        package_type = pkg_dict['type'] or 'dataset'

        errors = errors or {}
        error_summary = error_summary or {}
       
        
        vars = {'data': data, 'errors': errors,
                'error_summary': error_summary, 'action': 'new',
                'resource_form_snippet': self._resource_form(package_type),
                'dataset_type': package_type
                }
        vars['pkg_name'] = id
        # required for nav menu
        vars['pkg_dict'] = pkg_dict

        template = 'package/new_resource_not_draft.html'
              
              
        if pkg_dict['state'].startswith('draft'):
            vars['stage'] = ['complete', 'active']
            template = 'package/new_resource.html'
            
        return render(template, extra_vars=vars)
    
    def edit(self, id, data=None, errors=None, error_summary=None):
        package_type = self._get_package_type(id)
        context = {'model': model, 'session': model.Session,
                   'user': c.user, 'auth_user_obj': c.userobj,
                   'save': 'save' in request.params}

        if context['save'] and not data:
            return self._save_edit(id, context, package_type=package_type)
        try:
            c.pkg_dict = get_action('package_show')(dict(context,
                                                         for_view=True),
                                                    {'id': id})
            context['for_edit'] = True
            old_data = get_action('package_show')(context, {'id': id})
            # old data is from the database and data is passed from the
            # user if there is a validation error. Use users data if there.
            if data:
                old_data.update(data)
            data = old_data
        except (NotFound, NotAuthorized):
            abort(404, _('Dataset not found'))
        # are we doing a multiphase add?
        if data.get('state', '').startswith('draft'):
            c.form_action = h.url_for(controller='package', action='new')
            c.form_style = 'new'
            return self.new(data=data, errors=errors,
                            error_summary=error_summary)

        c.pkg = context.get("package")
       
        try:
            check_access('package_update', context)
        except NotAuthorized:
            abort(403, _('User %r not authorized to edit %s') % (c.user, id))
        # convert tags if not supplied in data
        if data and not data.get('tag_string'):
            data['tag_string'] = ', '.join(h.dict_list_reduce(
                c.pkg_dict.get('tags', {}), 'name'))
        errors = errors or {}
        form_snippet = self._package_form(package_type=package_type)
        form_vars = {'data': data, 'errors': errors,
                     'error_summary': error_summary, 'action': 'edit',
                     'dataset_type': package_type,
                     }
        #c.errors_json = h.json.dumps(errors)

        self._setup_template_variables(context, {'id': id},
                                       package_type=package_type)

        # we have already completed stage 1
        form_vars['stage'] = ['active']
        if data.get('state', '').startswith('draft'):
            form_vars['stage'] = ['active', 'complete']

        edit_template = self._edit_template(package_type)
        return render(edit_template,
                      extra_vars={'form_vars': form_vars,
                                  'form_snippet': form_snippet,
                                  'dataset_type': package_type})
    
         


    def resource_edit(self, id, resource_id, data=None, errors=None,
                      error_summary=None):
        ckan_url = config.get('ckan.site_url')
        euosme_path = config.get('ckan.CustomInspireDataset.euosme.path', "")
        context = {'model': model, 'session': model.Session,
                   'api_version': 3, 'for_edit': True,
                   'user': c.user, 'auth_user_obj': c.userobj}
        data_dict = {'id': id}

        try:
            check_access('package_update', context, data_dict)
        except NotAuthorized:
            abort(403, _('User %r not authorized to edit %s') % (c.user, id))

        if request.method == 'POST' and not data:
            data = data or \
                clean_dict(dict_fns.unflatten(tuplize_dict(parse_params(
                                                           request.POST))))
            # we don't want to include save as it is part of the form
            del data['save']

            data['package_id'] = id
            try:
                if resource_id:
                    data['id'] = resource_id
                    if(request.params.get('format')=='INSPIRE'):                       
                        home_dir = os.path.join(euosme_path)
                        old_name=request.POST['inspirenamen']
                        if(len(data ['url'])>0):
                            resource_name_xml = str(data['url'])
                            resource_name=resource_name_xml[0: len(resource_name_xml)-4]
                        else:
                            resource_name = old_name    
                        inspire_file_name = ""                        
                        if(os.path.exists(home_dir+"/"+resource_name+".xml")):
                            if(data["name"] and len(data ['name'])>0):
                                inspire_file_name = str(data["name"])                               
                            else:
                                inspire_file_name = old_name
                            descr = request.params.get('description')
                            if(descr):
                                descr = str(descr)
                            else:
                                descr = ""
                            api = c.userobj.apikey                            
                            filelocation=home_dir+'/'+resource_name+'.xml'
                            r = requests.post(ckan_url+'/api/action/resource_update',
                                  data={'package_id': id,
                                  'name': inspire_file_name,
                                  'id': resource_id,
                                  'format': 'INSPIRE',
                                  'description': descr,
                                  'url': 'upload',  # Needed to pass validation
                                  },                                
                                  headers={'Authorization': api},
                                  files=[('upload', file(filelocation))])
                        else:
                            get_action('resource_update')(context, data)  
                    else:                                  
                        get_action('resource_update')(context, data)
                else:
                    get_action('resource_create')(context, data)
            except ValidationError, e:
                errors = e.error_dict
                error_summary = e.error_summary
                return self.resource_edit(id, resource_id, data,
                                          errors, error_summary)
            except NotAuthorized:
                abort(403, _('Unauthorized to edit this resource'))
            h.redirect_to(controller='package', action='resource_read', id=id,
                          resource_id=resource_id)

        pkg_dict = get_action('package_show')(context, {'id': id})
        if pkg_dict['state'].startswith('draft'):
            # dataset has not yet been fully created
            resource_dict = get_action('resource_show')(context,
                                                        {'id': resource_id})
            return self.new_resource(id, data=resource_dict)
        # resource is fully created
        try:
            resource_dict = get_action('resource_show')(context,
                                                        {'id': resource_id})
        except NotFound:
            abort(404, _('Resource not found'))
        c.pkg_dict = pkg_dict
        c.resource = resource_dict
        # set the form action
        c.form_action = h.url_for(controller='package',
                                  action='resource_edit',
                                  resource_id=resource_id,
                                  id=id)
        if not data:
            data = resource_dict

        package_type = pkg_dict['type'] or 'dataset'

        errors = errors or {}
        error_summary = error_summary or {}
        if(data['format']=='INSPIRE'):
            is_inspire = '1'
        else:
            is_inspire = '0'       
        if(is_inspire == '1'):
            api = c.userobj.apikey
            inspire_file = data['name']+".xml"             
            inspire_file_name = str(resource_dict["name"])           
            url_inspire=str(data['url'])
            inspire_file_name = url_inspire[url_inspire.find('download')+len("download")+1:len(url_inspire)-4] 
            resp = requests.get(url_inspire,headers={'Authorization':  api})
            vars = {'data': data, 'errors': errors,
                'error_summary': error_summary, 'action': 'edit',
                'resource_form_snippet': self._resource_form(package_type),
                'dataset_type': package_type, 'is_inspire': is_inspire, 'inspire_xml': resp.content, 'inspire_file_name': inspire_file_name}
        else:                         
            vars = {'data': data, 'errors': errors,
                'error_summary': error_summary, 'action': 'edit',
                'resource_form_snippet': self._resource_form(package_type),
                'dataset_type': package_type, 'is_inspire': is_inspire, 'inspire_xml': '', 'inspire_file_name': ''}
        return render('package/cid_resource_edit.html', extra_vars=vars)
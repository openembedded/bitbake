// vim: set tabstop=4 expandtab ai:
//  BitBake Toaster Implementation
//
//  Copyright (C) 2013        Intel Corporation
//
//  This program is free software; you can redistribute it and/or modify
//  it under the terms of the GNU General Public License version 2 as
//  published by the Free Software Foundation.
//
//  This program is distributed in the hope that it will be useful,
//  but WITHOUT ANY WARRANTY; without even the implied warranty of
//  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
//  GNU General Public License for more details.
//
//  You should have received a copy of the GNU General Public License along
//  with this program; if not, write to the Free Software Foundation, Inc.,
//  51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

'use strict';

var angular_formpost = function($httpProvider) {
  // Use x-www-form-urlencoded Content-Type
  // By Ezekiel Victor, http://victorblog.com/2012/12/20/make-angularjs-http-service-behave-like-jquery-ajax/, no license, with attribution
  $httpProvider.defaults.headers.post['Content-Type'] = 'application/x-www-form-urlencoded;charset=utf-8';

  /**
   * The workhorse; converts an object to x-www-form-urlencoded serialization.
   * @param {Object} obj
   * @return {String}
   */
  var param = function(obj) {
    var query = '', name, value, fullSubName, subName, subValue, innerObj, i;

    for(name in obj) {
      value = obj[name];

      if(value instanceof Array) {
        for(i=0; i<value.length; ++i) {
          subValue = value[i];
          fullSubName = name + '[' + i + ']';
          innerObj = {};
          innerObj[fullSubName] = subValue;
          query += param(innerObj) + '&';
        }
      }
      else if(value instanceof Object) {
        for(subName in value) {
          subValue = value[subName];
          fullSubName = name + '[' + subName + ']';
          innerObj = {};
          innerObj[fullSubName] = subValue;
          query += param(innerObj) + '&';
        }
      }
      else if(value !== undefined && value !== null)
        query += encodeURIComponent(name) + '=' + encodeURIComponent(value) + '&';
    }

    return query.length ? query.substr(0, query.length - 1) : query;
  };

  // Override $http service's default transformRequest
  $httpProvider.defaults.transformRequest = [function(data) {
    return angular.isObject(data) && String(data) !== '[object File]' ? param(data) : data;
  }];
};


/**
 * Helper to execute callback on elements from array differences; useful for incremental UI updating.
 * @param  {Array} oldArray
 * @param  {Array} newArray
 * @param  {function} compareElements
 * @param  {function} onAdded
 * @param  {function} onDeleted
 *
 * no return
 */
function _diffArrays(existingArray, newArray, compareElements, onAdded, onDeleted ) {
    var added = [];
    var removed = [];
    newArray.forEach( function( newElement ) {
        var existingIndex = existingArray.findIndex(function ( existingElement ) {
                                return compareElements(newElement, existingElement);
                            });
        if (existingIndex < 0 && onAdded) { added.push(newElement); }
    });
    existingArray.forEach( function( existingElement ) {
        var newIndex = newArray.findIndex(function ( newElement ) {
                                return compareElements(newElement, existingElement);
                            });
        if (newIndex < 0 && onDeleted) { removed.push(existingElement); }
    });

    if (onAdded) {
        added.map(onAdded);
    }

    if (onDeleted) {
        removed.map(onDeleted);
    }

}

// add Array findIndex if not there

if (Array.prototype.findIndex === undefined) {
    Array.prototype.findIndex = function (callback) {
        var i = 0;
        for ( i = 0; i < this.length; i++ )
            if (callback(this[i], i, this)) return i;
        return -1;
    };
}

var projectApp = angular.module('project', ['ngCookies', 'ngAnimate', 'ui.bootstrap', 'ngRoute', 'ngSanitize'],  angular_formpost);

// modify the template tag markers to prevent conflicts with Django
projectApp.config(function($interpolateProvider) {
    $interpolateProvider.startSymbol("{[");
    $interpolateProvider.endSymbol("]}");
});


// add time interval to HH:mm filter
projectApp.filter('timediff', function() {
    return function(input) {
        function pad(j) {
            if (parseInt(j) < 10) {return "0" + j;}
            return j;
        }
        var seconds = parseInt(input);
        var minutes = Math.floor(seconds / 60);
        seconds = seconds - minutes * 60;
        var hours = Math.floor(minutes / 60);
        minutes = minutes - hours * 60;
        return pad(hours) + ":" + pad(minutes) + ":" + pad(seconds);
    };
});

// add "time to future" eta that computes time from now to a point in the future
projectApp.filter('toeta', function() {
    return function(input) {
       var crtmiliseconds = new Date().getTime();
        diff = (parseInt(input) - crtmiliseconds ) / 1000;
        console.log("Debug: future time ", input, "crt time", crtmiliseconds, ":", diff);
        return diff < 0 ? 300 : diff;
    };
});

/**
 * main controller for the project page
 */

projectApp.controller('prjCtrl', function($scope, $modal, $http, $interval, $location, $cookies, $cookieStore, $q, $sce, $anchorScroll, $animate, $sanitize) {

    /**
     * Retrieves text suggestions for text-edit drop down autocomplete boxes
     */

    $scope.getLayersAutocompleteSuggestions = function(currentValue) {
        var deffered = $q.defer();

        $http({method:"GET", url: $scope.urls.layers, params : { search: currentValue, format: "json" }})
            .success(function (_data) {
                if (_data.error != "ok") {
                    console.warn("error on data", _data.error);
                    deffered.reject(_data.error);
                }
                deffered.resolve(_data.rows);
            });

        return deffered.promise;
    }

    $scope.filterProjectLayerIds = function () {
        return $scope.layers.map(function (e) { return e.id; });
    }

    $scope.getMachinesAutocompleteSuggestions = function(currentValue) {
        var deffered = $q.defer();

        $http({method:"GET", url: $scope.urls.machines, params : { search: currentValue, format: "json" }})
            .success(function (_data) {
                if (_data.error != "ok") {
                    console.warn("error on data", _data.error);
                    deffered.reject(_data.error);
                }
                deffered.resolve(_data.rows);
            });

        return deffered.promise;
    }

    $scope.getRecipesAutocompleteSuggestions = function(currentValue) {
        var deffered = $q.defer();

        $http({method:"GET", url: $scope.urls.targets, params : { search: currentValue, format: "json" }})
            .success(function (_data) {
                if (_data.error != "ok") {
                    console.warn("error on data", _data.error);
                    deffered.reject(_data.error);
                }
                deffered.resolve(_data.rows);
            });
        return deffered.promise;
    }

    $scope.values = function() {
        var deffered = $q.defer();

        deffered.resolve(["mama", "tata"]);

        return deffered.promise;
    };

    $scope.getAutocompleteSuggestions = function(type, currentValue) {
        var deffered = $q.defer();

        $http({method:"GET", url: $scope.urls.xhr_datatypeahead, params : { type: type, search: currentValue}})
            .success(function (_data) {
                if (_data.error != "ok") {
                    console.warn(_data.error);
                    deffered.reject(_data.error);
                }
                deffered.resolve(_data.rows);
            });

        return deffered.promise;
    };

    var inXHRcall = false;

    /**
     * XHR call wrapper that automatically handles errors and auto-updates the page content to reflect project state on server side.
     */
    $scope._makeXHRCall = function(callparams) {
        if (inXHRcall) {
            if (callparams.data === undefined) {
                // we simply skip the data refresh calls
                console.warn("TRC1: race on XHR, aborted");
                return;
            } else {
                // we return a promise that we'll solve by reissuing the command later
                var delayed = $q.defer();
                console.warn("TRC2: race on XHR, delayed");
                $interval(function () {$scope._makeXHRCall(callparams).then(function (d) { delayed.resolve(d); });}, 100, 1);

                return delayed.promise;
            }

        }
        var deffered = $q.defer();

        /* we only talk in JSON to the server */
        if (callparams.method == 'GET') {
            if (callparams.data === undefined) {
                callparams.data = {};
            }
            callparams.data.format = "json";
        } else {
            if (callparams.url.indexOf("?") > -1) {
              callparams.url = callparams.url.split("?").map(function (element, index) {
                if (index == 1) {
                    var elements = [];
                    if (element.indexOf("&")>-1) {
                        elements = element.split("&");
                    }
                    elements.push("format=json");
                    element = elements.join("&");
                }
                return element;
              }).join("?");
            } else {
              callparams.url += "?format=json";
            }
        }


        if (undefined === callparams.headers) { callparams.headers = {}; }
        callparams.headers['X-CSRFToken'] = $cookies.csrftoken;

        $http(callparams).success(function(_data, _status, _headers, _config) {
            if (_data.error != "ok") {
                console.warn("Failed XHR request (" + _status + "): " + _data.error);
                console.error("Failed XHR request: ", _data, _status, _headers, _config);
                // stop refreshing hte page
                $interval.cancel($scope.pollHandle);
                deffered.reject(_data.error);
            }
            else {
                if (_data.layers !== undefined) {

                    var addedLayers = [];
                    var deletedLayers = [];

                    // step 1 - delete entries not found
                    $scope.layers.forEach(function (elem) {
                        if (-1 == _data.layers.findIndex(function (elemX) { return elemX.id == elem.id && elemX.name == elem.name; })) {
                            deletedLayers.push(elem);
                        }
                    });
                    deletedLayers.forEach(function (elem) {
                            $scope.layers.splice($scope.layers.indexOf(elem),1);
                    });
                    // step 2 - merge new entries
                    _data.layers.forEach(function (elem) {
                        var found = false;
                        var i;
                        for (i = 0 ; i < $scope.layers.length; i ++) {
                            if ($scope.layers[i].orderid < elem.orderid) continue;
                            if ($scope.layers[i].orderid == elem.orderid) {
                                found = true; break;
                            }
                            if ($scope.layers[i].orderid > elem.orderid) break;
                        }
                        if (!found) {
                            $scope.layers.splice(i, 0, elem);
                            addedLayers.push(elem);
                        }
                    });

                    // step 3 - display alerts.
                    if (addedLayers.length > 0) {
                        $scope.displayAlert($scope.zone2alerts,
                            "You have added <b>"+addedLayers.length+"</b> layer" + ((addedLayers.length>1)?"s: ":": ") + addedLayers.map(function (e) { return "<a href=\""+e.layerdetailurl+"\">"+e.name+"</a>"; }).join(", "),
                            "alert-info");
                        // invalidate error layer data based on current layers
                        $scope.layersForTargets = {};
                    }
                    if (deletedLayers.length > 0) {
                        $scope.displayAlert($scope.zone2alerts, "You have deleted <b>"+deletedLayers.length+"</b> layer" + ((deletedLayers.length>1)?"s: ":": ") + deletedLayers.map(function (e) { return "<a href=\""+e.layerdetailurl+"\">"+e.name+"</a>"; }).join(", "), "alert-info");
                        // invalidate error layer data based on current layers
                        $scope.layersForTargets = {};
                    }

                }


                if (_data.builds !== undefined) {
                    var toDelete = [];
                    // step 1 - delete entries not found
                    $scope.builds.forEach(function (elem) {
                        if (-1 == _data.builds.findIndex(function (elemX) { return elemX.id == elem.id; })) {
                            toDelete.push(elem);
                        }
                    });
                    toDelete.forEach(function (elem) {
                        $scope.builds.splice($scope.builds.indexOf(elem),1);
                    });
                    // step 2 - merge new entries
                    _data.builds.forEach(function (elem) {
                        var found = false;
                        var i = 0;
                        for (i = 0 ; i < $scope.builds.length; i ++) {
                            if ($scope.builds[i].id > elem.id) continue;
                            if ($scope.builds[i].id == elem.id) {
                                found=true;
                                // do deep data copy
                                for (var attr in elem) {
                                    $scope.builds[i][attr] = elem[attr];
                                }
                                break;
                            }
                            if ($scope.builds[i].id < elem.id) break;
                        }
                        if (!found) {
                            $scope.builds.splice(i, 0, elem);
                        }
                    });
                    // step 3 - merge "Canceled" builds
                    $scope.canceledBuilds.forEach(function (elem) {
                        // mock the build object
                        var found = false;
                        var i = 0;
                        for (i = 0; i < $scope.builds.length; i ++) {
                            if ($scope.builds[i].id > elem.id) continue;
                            if ($scope.builds[i].id == elem.id) { found=true; break; }
                            if ($scope.builds[i].id < elem.id) break;
                        }
                        if (!found) {
                            $scope.builds.splice(i, 0, elem);
                        }
                    });


                    $scope.fetchLayersForTargets();
                }
                if (_data.targets !== undefined) {
                    $scope.targets = _data.targets;
                }
                if (_data.machine !== undefined) {
                    $scope.machine = _data.machine;
                }
                if (_data.user !== undefined) {
                    $scope.user = _data.user;
                }

                if (_data.prj !== undefined) {
                    $scope.project = _data.prj;

                    // update breadcrumb, outside the controller
                    $('#project_name').text($scope.project.name);
                }

                $scope.validateData();
                inXHRcall = false;
                deffered.resolve(_data);
            }
        }).error(function(_data, _status, _headers, _config) {
            if (_status === 0) {
                // the server has gone away
                // alert("The server is not responding. The application will terminate now");
                $interval.cancel($scope.pollHandle);
            }
            else {
                console.error("Failed HTTP XHR request: ", _data, _status, _headers, _config);
                inXHRcall = false;
                deffered.reject(_data.error);
            }
        });

        return deffered.promise;
    };

    $scope.layeralert = undefined;
    /**
     * Verifies and shows user alerts on invalid project data
     */

    $scope.validateData = function () {
        if ($scope.project.release) {
            if ($scope.layers.length === 0) {
            $scope.layeralert = $scope.displayAlert($scope.zone1alerts, "You need to add some layers to this project. <a href=\""+$scope.urls.layers+"\">View all layers available in Toaster</a> or <a href=\""+$scope.urls.importlayer+"\">import a layer</a>");
            } else {
                if ($scope.layeralert !== undefined) {
                    $scope.layeralert.close();
                    $scope.layeralert = undefined;
                }
            }
        } else {
            $scope.layeralert = $scope.displayAlert($scope.zone1alerts, "This project is not set to run builds.");
        }
    };

    $scope.buildExistingTarget = function(targets) {
         $scope.buildTargetList(targets.map(function(v){return ((v.task) ? v.target + ":" + v.task : v.target);}));
    };

    $scope.buildTargetList = function(targetlist) {
        var oldTargetName = $scope.targetName;
        $scope.targetName = targetlist.join(' ');
        $scope.buildNamedTarget();
        $scope.targetName = oldTargetName;
    };

    $scope.buildNamedTarget = function() {
        if ($scope.targetName === undefined && $scope.targetName1 === undefined){
            console.warn("No target defined, please type in a target name");
            return;
        }

        // this writes the $scope.safeTargetName variable
        $scope.sanitizeTargetName();

        $scope._makeXHRCall({
            method: "POST", url: $scope.urls.xhr_build,
            data : {
                targets: $scope.safeTargetName,
            }
        }).then(function (data) {
            // make sure nobody re-uses the current $safeTargetName
            delete $scope.safeTargetName;
            console.warn("TRC3: received ", data);
            $scope.targetName = undefined;
            $scope.targetName1 = undefined;
            $location.hash('buildslist');
            // call $anchorScroll()
            $anchorScroll();
        });
    };

    $scope.sanitizeTargetName = function() {
        $scope.safeTargetName = undefined;
        if (undefined === $scope.targetName) $scope.safeTargetName = $scope.targetName1;
        if (undefined === $scope.targetName1) $scope.safeTargetName = $scope.targetName;

        if (undefined === $scope.safeTargetName) return;

        $scope.safeTargetName = $scope.safeTargetName.replace(/\[.*\]/, '').trim();
    };

    $scope.buildCancel = function(build) {
        $scope._makeXHRCall({
            method: "POST", url: $scope.urls.xhr_build,
            data: {
                buildCancel: build.id,
            }
        }).then( function () {
            build.status = "deleted";
            $scope.canceledBuilds.push(build);
        });
    };

    $scope.buildDelete = function(build) {
        $scope.canceledBuilds.splice($scope.canceledBuilds.indexOf(build), 1);
    };


    $scope.onLayerSelect = function (item, model, label) {
        $scope.layerToAdd = item;
        $scope.layerAddName = item.layer__name;
    };

    $scope.machineSelect = function (machineName) {
        $scope._makeXHRCall({
            method: "POST", url: $scope.urls.xhr_edit,
            data: {
              machineName:  machineName,
            }
        }).then(function () {
          $scope.machine.name = machineName;

          $scope.displayAlert($scope.zone2alerts, "You have changed the machine to: <strong>" + $scope.machine.name + "</strong>", "alert-info");
          var machineDistro = angular.element("#machine-distro");

          angular.element("html, body").animate({ scrollTop: machineDistro.position().top }, 700).promise().done(function() {
            $animate.addClass(machineDistro, "machines-highlight");
          });
        });
    };


    $scope.layerAdd = function() {

        $http({method:"GET", url: $scope.layerToAdd.layerDetailsUrl, params : {format: "json"}})
        .success(function (_data) {
             if (_data.error != "ok") {
                 console.warn(_data.error);
             } else {
                /* filter out layers that are already in the project */
                var filtered_list = [];
                var projectlayers_ids = $scope.layers.map(function (e) { return e.id });
                for (var i = 0; i < _data.layerdeps.list.length; i++) {
                    if (projectlayers_ids.indexOf(_data.layerdeps.list[i].id) == -1) {
                        filtered_list.push( _data.layerdeps.list[i]);
                    }
                }

                _data.layerdeps.list = filtered_list;
                if (_data.layerdeps.list.length > 0) {
                     // activate modal
                     console.log("listing modals");
                     var modalInstance = $modal.open({
                       templateUrl: 'dependencies_modal',
                       controller: function ($scope, $modalInstance, items, layerAddName) {
                         $scope.items =  items;
                         $scope.layerAddName = layerAddName;
                         $scope.selectedItems = (function () {
                                var s = {};
                                for (var i = 0; i < items.length; i++)
                                    { s[items[i].id] = true; }
                                return s;
                            })();

                         $scope.ok = function() {
                            console.warn("TRC4: scope selected is ", $scope.selectedItems);
                            $modalInstance.close(Object.keys($scope.selectedItems).filter(function (e) { return $scope.selectedItems[e];}));
                         };

                         $scope.cancel = function() {
                            $modalInstance.dismiss('cancel');
                         };

                         $scope.update = function() {
                            console.warn("TRC5: updated ", $scope.selectedItems);
                         };
                       },
                       resolve: {
                         items: function () {
                             return _data.layerdeps.list;
                         },
                         layerAddName: function () {
                             return $scope.layerAddName;
                         },
                       }
                     });
                     console.log("built modal instance", modalInstance);

                     modalInstance.result.then(function (selectedArray) {
                         selectedArray.push($scope.layerToAdd.id);
                         console.warn("TRC6: selected", selectedArray);

                         $scope._makeXHRCall({
                             method: "POST", url: $scope.urls.xhr_edit,
                             data: {
                                 layerAdd: selectedArray.join(","),
                             }
                         }).then(function () {
                             $scope.adjustMostBuiltItems(selectedArray.length);
                             $scope.layerAddName = undefined;
                         });
                     });
                 }
                 else {
                         $scope.adjustMostBuiltItems(1);
                         $scope._makeXHRCall({
                             method: "POST", url: $scope.urls.xhr_edit,
                             data: {
                                 layerAdd:  $scope.layerToAdd.id,
                             }
                         }).then(function () {
                             $scope.layerAddName = undefined;
                         });
                 }
             }
         });
    };

    $scope.layerDel = function(id) {
        $scope.adjustMostBuiltItems(-1);
        $scope._makeXHRCall({
            method: "POST", url: $scope.urls.xhr_edit,
            data: {
                layerDel: id,
            }
        });
    };

    $scope.adjustMostBuiltItems = function(listDelta) {
        $scope.layerCount += listDelta;
        $scope.mutedtargets = ($scope.layerCount == 0 ? "muted" : "");
    };

/*
*/


    /**
     * Verifies if a project settings change would trigger layer updates. If user confirmation is needed,
     * a modal dialog will prompt the user to ack the changes. If not, the editProjectSettings() function is called directly.
     *
     * Only "versionlayers" change for is supported (and hardcoded) for now.
     */

    $scope.testProjectSettingsChange = function(elementid) {
        if (elementid != '#change-project-version') throw "Not implemented";

        $http({method:"GET", url: $scope.urls.xhr_datatypeahead, params : { type: "versionlayers", search: $scope.projectVersion }}).
        success(function (_data) {
            if (_data.error != "ok") {
                alert (_data.error);
            }
            else {
                 if (_data.rows.length > 0) {
                     // activate modal
                     var modalInstance = $modal.open({
                       templateUrl: 'change_version_modal',
                       controller: function ($scope, $modalInstance, items, releaseName, releaseDescription) {
                         $scope.items =  items;
                         $scope.releaseName = releaseName;
                         $scope.releaseDescription = releaseDescription;

                         $scope.ok = function() {
                             $modalInstance.close();
                         };

                         $scope.cancel = function() {
                             $modalInstance.dismiss('cancel');
                         };

                       },
                       resolve: {
                         items: function () {
                             return _data.rows;
                         },
                         releaseName: function () {
                             return $scope.releases.filter(function (e) { if (e.id == $scope.projectVersion) return e;})[0].name;
                         },
                         releaseDescription: function () {
                             return $scope.releases.filter(function (e) { if (e.id == $scope.projectVersion) return e;})[0].description;
                         },
                       }
                     });

                     modalInstance.result.then(function () { $scope.editProjectSettings(elementid); });
                 } else {
                    $scope.editProjectSettings(elementid);
                 }
            }
        });
    };

    /**
     * Performs changes to project settings, and updates the user interface accordingly.
     */

    $scope.editProjectSettings = function(elementid) {
        var data = {};
        console.warn("TRC7: editProjectSettings with ", elementid);
        var alertText;
        var alertZone;
        var oldLayers = [];

        switch(elementid) {
            case '#select-machine':
                alertText = "You have changed the machine to: <strong>" + $scope.machineName + "</strong>";
                alertZone = $scope.zone2alerts;
                data.machineName = $scope.machineName;
                break;
            case '#change-project-name':
                data.projectName = $scope.projectName;
                alertText = "You have changed the project name to: <strong>" + $scope.projectName + "</strong>";
                alertZone = $scope.zone3alerts;
                break;
            case '#change-project-version':
                data.projectVersion = $scope.projectVersion;
                alertText = "You have changed the release to: ";
                alertZone = $scope.zone3alerts;
                // save old layers
                oldLayers = $scope.layers.slice(0);
                break;
            default:
                throw "FIXME: implement conversion for element " + elementid;
        }

        $scope._makeXHRCall({
            method: "POST", url: $scope.urls.xhr_edit, data: data,
        }).then( function (_data) {
            $scope.toggle(elementid);
            if (data.projectVersion !== undefined) {
                alertText += "<strong>" + $scope.project.release.desc + "</strong>. ";
            }
            if (elementid == '#change-project-version') {
                $scope.layersForTargets = {};   // invalidate error layers for the targets, since layers changed

                // requirement https://bugzilla.yoctoproject.org/attachment.cgi?id=2229, notification for changed version to include layers
                $scope.zone2alerts.forEach(function (e) { e.close(); });


                // warnings - this is executed AFTER the generic XHRCall handling is done; at this point,
                if (_data.layers !== undefined) {
                    // show added/deleted layer notifications; scope.layers is already updated by this point.
                    var addedLayers = [];
                    var deletedLayers = [];
                    _diffArrays( oldLayers, $scope.layers, function (e, f) { return e.id == f.id; },
                        function (e) {addedLayers.push(e); },
                        function (e) {deletedLayers.push(e); });

                    var hasDifferentLayers = (addedLayers.length || deletedLayers.length)
                    if (hasDifferentLayers) {
                        alertText += "This has caused the following changes in your project layers:<ul>";
                    }
                    // some of the deleted layers are actually replaced (changed) layers
                    var changedLayers = [];
                    deletedLayers.forEach(function (e) {
                        if ( -1 < addedLayers.findIndex(function (f) { return f.name == e.name; })) {
                            changedLayers.push(e);
                        }
                    });

                    changedLayers.forEach(function (e) {
                        deletedLayers.splice(deletedLayers.indexOf(e), 1);
                    });

                    if (addedLayers.length > 0) {
                        alertText += "<li><strong>"+addedLayers.length+"</strong> layer" + ((addedLayers.length>1)?"s":"") + " changed to the <strong> " + $scope.project.release.name + " </strong> branch: " + addedLayers.map(function (e) { return "<a href=\""+e.layerdetailurl+"\">"+e.name+"</a>"; }).join(", ") + "</li>";
                    }
                    if (deletedLayers.length > 0) {
                        alertText += "<li><strong>"+deletedLayers.length+"</strong> layer" + ((deletedLayers.length>1)?"s":"") + " deleted: " + deletedLayers.map(function (e) { return "<a href=\""+e.layerdetailurl+"\">"+e.name+"</a>"; }).join(", ") + "</li>";
                    }

                }
                if (hasDifferentLayers) {
                    alertText += "</ul>";
                }
            }
            $scope.displayAlert(alertZone, alertText, "alert-info");
        });
    };


    /**
     * Extracts a command passed through the local path in location, and executes/updates UI based on the command
     */

    $scope.updateDisplayWithCommands = function() {

        function _cmdExecuteWithParam(param, f) {
            var cmd = $location.path();
            if (cmd.indexOf(param) === 0) {
                if (cmd.indexOf("=") > -1) {
                    var parameter = cmd.split("=", 2)[1];
                    if (parameter !== undefined && parameter.length > 0) {
                        f(parameter);
                    }
                } else {
                    f();
                }
            }
        }

        _cmdExecuteWithParam("/newproject", function () {
            $scope.displayAlert($scope.zone1alerts,
                    "Your project <strong>" + $scope.project.name +
                    "</strong> has been created. You can now <a href=\""+ $scope.urls.layers +
                    "\">add layers</a> and <a href=\""+ $scope.urls.targets +
                    "\">select recipes</a> you want to build.", "alert-success");
        });

        _cmdExecuteWithParam("/layerimported", function () {
          var imported = $cookieStore.get("layer-imported-alert");
          var text;

          if (!imported)
            return;

          if (imported.deps_added.length === 0) {
            text = "You have imported <strong><a href=\""+imported.imported_layer.layerDetailsUrl+"\">"+imported.imported_layer.name+
              "</a></strong> and added it to your project.";
          } else {
            var links = "<a href=\""+$scope.urls.layer+
              imported.imported_layer.id+"\">"+imported.imported_layer.name+
              "</a>, ";

            imported.deps_added.map (function(item, index){
              links +="<a href=\""+item.layerDetailsUrl+"\" >"+item.name+
                "</a>";
              /*If we're at the last element we don't want the trailing comma */
              if (imported.deps_added[index+1] !== undefined)
                links += ", ";
            });

            /* Length + 1 here to do deps + the imported layer */
            text = "You have imported <strong><a href=\""+$scope.urls.layer+
              imported.imported_layer.id+"\">"+imported.imported_layer.name+
              "</a></strong> and added <strong>"+(imported.deps_added.length+1)+
              "</strong> layers to your project: <strong>"+links+"</strong>";
          }

            $scope.displayAlert($scope.zone2alerts, text, "alert-info");
            // This doesn't work
            $cookieStore.remove("layer-imported-alert");
            //use jquery plugin instead
            $.removeCookie("layer-imported-alert", { path: "/"});
        });

        _cmdExecuteWithParam("/targetbuild=", function (targets) {
            var oldTargetName = $scope.targetName;
            $scope.targetName = targets.split(",").join(" ");
            $scope.buildNamedTarget();
            $scope.targetName = oldTargetName;
            $location.path('');
        });

        _cmdExecuteWithParam("/machineselect=", function (machine) {
            $scope.machineName = machine;
            $scope.machine.name = machine;
            $scope.machineSelect(machine);

        });


        _cmdExecuteWithParam("/layeradd=", function (layer) {
                $scope.layerToAdd = layer;
                $scope.layerAdd();
        });
    };

    /**
     * Utility function to display an alert to the user
     */

    $scope.displayAlert = function(zone, text, type) {
        if (zone.maxid === undefined) { zone.maxid = 0; }
        var crtid = zone.maxid ++;
        angular.forEach(zone, function (o) { o.close(); });
        var o = {
            id: crtid, text: text, type: type,
            close: function() {
                zone.splice((function(id) {
                    for (var i = 0; i < zone.length; i++)
                        if (id == zone[i].id)
                            { return i; }
                    return undefined;
                    }) (crtid), 1);
               },
            };
        zone.push(o);
        return o;
    };

    /**
     * Toggles display items between label and input box (the edit pencil icon) on selected settings in project page
     */

    $scope.toggle = function(id) {
        $scope.projectName = $scope.project.name;
        $scope.projectVersion = $scope.project.release.id;
        $scope.machineName = $scope.machine.name;

        angular.element(id).toggle();
        angular.element(id+"-opposite").toggle();
    };

    /**
     * Functionality related to "Most build targets"
     */

    $scope.enableBuildSelectedTargets = function () {
        var keys = Object.keys($scope.mostBuiltTargets);
        keys = keys.filter(function (e) { if ($scope.mostBuiltTargets[e]) return e; });
        return keys.length === 0;
    };

    $scope.disableBuildCheckbox = function(t) {
        if ( $scope.layerCount == 0 ) {
            $scope.mostBuiltTargets[t] = 0;
            return true;
        };
        return false;
    }

    $scope.buildSelectedTargets = function () {
        var keys = Object.keys($scope.mostBuiltTargets);
        keys = keys.filter(function (e) { if ($scope.mostBuiltTargets[e]) return e; });

        $scope.buildTargetList(keys);
        for (var i = 0; i < keys.length; i++)
        {
            $scope.mostBuiltTargets[keys[i]] = 0;
        }
    };

    /**
     * Helper function to deal with error string recognition and manipulation
     */

    $scope.getTargetNameFromErrorMsg = function (msg) {
        return msg.split(" ").splice(2).map(function (v) { return v.replace(/'/g, ''); });
    };

    /**
     * Utility function to retrieve which layers can be added to the project if the target was not
     * provided by any of the existing project layers
     */

    $scope.fetchLayersForTargets = function () {
        $scope.builds.forEach(function (buildrequest) {
            buildrequest.errors.forEach(function (error) {
                if (error.msg.indexOf("Nothin") === 0) {
                    $scope.getTargetNameFromErrorMsg(error.msg).forEach(function (target) {
                        if ($scope.layersForTargets[target] === undefined)
                        $scope.getAutocompleteSuggestions("layers4target", target).then( function (list) {
                            $scope.layersForTargets[target] = list;
                        });
                    });
                }
            });
        });
    };


    /**
     * Page init code - just init variables and set the automated refresh
     */

    $scope.init = function() {
        $scope.canceledBuilds = [];
        $scope.layersForTargets = {};
        $scope.fetchLayersForTargets();
        $scope.pollHandle = $interval(function () { $scope._makeXHRCall({method: "GET", url: $scope.urls.xhr_edit, data: undefined});}, 2000, 0);
    };

});


var _testing_scope;

function test_set_alert(text) {
    _testing_scope = angular.element("div#main").scope();
    _testing_scope.displayAlert(_testing_scope.zone3alerts, text);
    console.warn("TRC8: zone3alerts", _testing_scope.zone3alerts);
    _testing_scope.$digest();
}

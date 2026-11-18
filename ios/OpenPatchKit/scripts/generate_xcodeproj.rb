#!/usr/bin/env ruby
# Generates OpenPatchKit.xcodeproj (frameworks OpenPatchCore, OpenPatchKit, OpenPatchKitUI + OpenPatchKitTests).
#
# Requires the `xcodeproj` gem (ships with CocoaPods):
#   GEM_HOME=$(dirname $(dirname $(readlink -f $(which pod))))/libexec ruby scripts/generate_xcodeproj.rb
# The generated project resolves LoopKit/LoopKitUI via BUILT_PRODUCTS_DIR, i.e. it must be built from a
# workspace that also contains LoopKit.xcodeproj (Trio.xcworkspace does).
require 'fileutils'
require 'xcodeproj'

ROOT = File.expand_path('..', __dir__)
PROJECT_PATH = File.join(ROOT, 'OpenPatchKit.xcodeproj')
DEPLOYMENT = '17.0'

FileUtils.rm_rf(PROJECT_PATH)
project = Xcodeproj::Project.new(PROJECT_PATH)
project.root_object.development_region = 'en'
project.root_object.known_regions = %w[en de Base]

# Signing team comes from Trio's ConfigOverride.xcconfig when the kit sits next to / inside a Trio checkout.
config_ref = project.main_group.new_file('Support/Config.xcconfig')
project.build_configurations.each { |c| c.base_configuration_reference = config_ref }

def common_settings(target, bundle_id, extra = {})
  target.build_configurations.each do |config|
    s = config.build_settings
    s['PRODUCT_BUNDLE_IDENTIFIER'] = bundle_id
    s['IPHONEOS_DEPLOYMENT_TARGET'] = DEPLOYMENT
    s['SWIFT_VERSION'] = '5.0'
    s['SDKROOT'] = 'iphoneos'
    s['SUPPORTED_PLATFORMS'] = 'iphoneos iphonesimulator'
    s['TARGETED_DEVICE_FAMILY'] = '1,2'
    s['GENERATE_INFOPLIST_FILE'] = 'YES'
    s['CURRENT_PROJECT_VERSION'] = '1'
    s['MARKETING_VERSION'] = '0.1.0'
    s['CODE_SIGN_STYLE'] = 'Automatic'
    s['ENABLE_USER_SCRIPT_SANDBOXING'] = 'NO'
    s['FRAMEWORK_SEARCH_PATHS'] = ['$(inherited)', '$(BUILT_PRODUCTS_DIR)']
    s['LD_RUNPATH_SEARCH_PATHS'] = ['$(inherited)', '@executable_path/Frameworks', '@loader_path/Frameworks']
    s.merge!(extra)
  end
end

def framework_settings(name)
  {
    'DEFINES_MODULE' => 'YES',
    'SKIP_INSTALL' => 'YES',
    'INFOPLIST_KEY_NSHumanReadableCopyright' => 'OpenPatch contributors',
    'DYLIB_INSTALL_NAME_BASE' => '@rpath',
    'INSTALL_PATH' => '$(LOCAL_LIBRARY_DIR)/Frameworks',
    'BUILD_LIBRARY_FOR_DISTRIBUTION' => 'NO',
    'PRODUCT_NAME' => '$(TARGET_NAME:c99extidentifier)',
    'SWIFT_EMIT_LOC_STRINGS' => 'NO'
  }.tap { |h| h['MODULEMAP_FILE'] = nil; h.delete('MODULEMAP_FILE') }
end

def add_sources(project, target, dir, group_name)
  group = project.main_group.new_group(group_name, dir)
  files = Dir.glob(File.join(ROOT, dir, '**', '*.swift')).sort
  refs = files.map do |file|
    rel = file.sub("#{File.join(ROOT, dir)}/", '')
    # keep folder structure as groups
    parts = rel.split('/')
    g = group
    parts[0..-2].each { |p| g = g[p] || g.new_group(p, p) }
    g.new_reference(parts.last)
  end
  target.add_file_references(refs)
  group
end

def add_localized_strings(project, target, group, dir)
  variant = group.new_variant_group('Localizable.strings')
  %w[en de].each do |lang|
    ref = variant.new_reference("Resources/#{lang}.lproj/Localizable.strings")
    ref.name = lang
  end
  target.resources_build_phase.add_file_reference(variant)
end

def add_header(project, target, header_name)
  group = project.main_group['Support'] || project.main_group.new_group('Support', 'Support')
  ref = group.new_reference("#{header_name}.h")
  build_file = target.headers_build_phase.add_file_reference(ref)
  build_file.settings = { 'ATTRIBUTES' => ['Public'] }
  target.build_configurations.each do |c|
    c.build_settings['INFOPLIST_FILE'] = nil
    c.build_settings.delete('INFOPLIST_FILE')
  end
end

def system_framework(project, target, name)
  ref = project.frameworks_group.new_reference("System/Library/Frameworks/#{name}.framework")
  ref.source_tree = 'SDKROOT'
  ref.last_known_file_type = 'wrapper.framework'
  target.frameworks_build_phase.add_file_reference(ref)
end

def products_framework(project, target, name)
  ref = project.frameworks_group.files.find { |f| f.path == "#{name}.framework" && f.source_tree == 'BUILT_PRODUCTS_DIR' }
  unless ref
    ref = project.frameworks_group.new_reference("#{name}.framework")
    ref.source_tree = 'BUILT_PRODUCTS_DIR'
    ref.explicit_file_type = 'wrapper.framework'
    ref.last_known_file_type = nil
  end
  target.frameworks_build_phase.add_file_reference(ref)
end

# --- OpenPatchCore -----------------------------------------------------------------------------
core = project.new_target(:framework, 'OpenPatchCore', :ios, DEPLOYMENT)
common_settings(core, 'org.openpatch.OpenPatchCore', framework_settings('OpenPatchCore'))
core_group = project.main_group.new_group('OpenPatchCore', 'OpenPatchCore/Sources/OpenPatchCore')
Dir.glob(File.join(ROOT, 'OpenPatchCore/Sources/OpenPatchCore/*.swift')).sort.each do |file|
  core.add_file_references([core_group.new_reference(File.basename(file))])
end
add_header(project, core, 'OpenPatchCore')

# --- OpenPatchKit ------------------------------------------------------------------------------
kit = project.new_target(:framework, 'OpenPatchKit', :ios, DEPLOYMENT)
common_settings(kit, 'org.openpatch.OpenPatchKit', framework_settings('OpenPatchKit'))
kit_group = add_sources(project, kit, 'OpenPatchKit', 'OpenPatchKit')
add_localized_strings(project, kit, kit_group, 'OpenPatchKit')
add_header(project, kit, 'OpenPatchKit')
kit.add_dependency(core)
products_framework(project, kit, 'OpenPatchCore')
products_framework(project, kit, 'LoopKit')
%w[CoreBluetooth HealthKit].each { |f| system_framework(project, kit, f) }

# --- OpenPatchKitUI ----------------------------------------------------------------------------
ui = project.new_target(:framework, 'OpenPatchKitUI', :ios, DEPLOYMENT)
common_settings(ui, 'org.openpatch.OpenPatchKitUI', framework_settings('OpenPatchKitUI'))
ui_group = add_sources(project, ui, 'OpenPatchKitUI', 'OpenPatchKitUI')
add_localized_strings(project, ui, ui_group, 'OpenPatchKitUI')
add_header(project, ui, 'OpenPatchKitUI')
ui.add_dependency(kit)
ui.add_dependency(core)
%w[OpenPatchKit OpenPatchCore LoopKit LoopKitUI].each { |f| products_framework(project, ui, f) }
%w[SwiftUI CoreBluetooth HealthKit].each { |f| system_framework(project, ui, f) }

# --- OpenPatchKitTests -------------------------------------------------------------------------
tests = project.new_target(:unit_test_bundle, 'OpenPatchKitTests', :ios, DEPLOYMENT)
common_settings(tests, 'org.openpatch.OpenPatchKitTests', { 'SKIP_INSTALL' => 'YES' })
add_sources(project, tests, 'OpenPatchKitTests', 'OpenPatchKitTests')
tests.add_dependency(kit)
tests.add_dependency(core)
%w[OpenPatchKit OpenPatchCore LoopKit].each { |f| products_framework(project, tests, f) }
system_framework(project, tests, 'HealthKit')

project.save

# --- Shared scheme -----------------------------------------------------------------------------
scheme = Xcodeproj::XCScheme.new
[core, kit, ui, tests].each { |t| scheme.add_build_target(t, t != tests) }
scheme.add_test_target(tests)
scheme.save_as(PROJECT_PATH, 'OpenPatchKit', true)
puts "Generated #{PROJECT_PATH}"

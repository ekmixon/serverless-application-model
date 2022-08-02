import yaml
from yaml import ScalarNode, SequenceNode
from six import string_types

# This helper copied almost entirely from
# https://github.com/aws/aws-cli/blob/develop/awscli/customizations/cloudformation/yamlhelper.py


def yaml_parse(yamlstr):
    """Parse a yaml string"""
    yaml.SafeLoader.add_multi_constructor("!", intrinsics_multi_constructor)
    return yaml.safe_load(yamlstr)


def intrinsics_multi_constructor(loader, tag_prefix, node):
    """
    YAML constructor to parse CloudFormation intrinsics.
    This will return a dictionary with key being the instrinsic name
    """

    # Get the actual tag name excluding the first exclamation
    tag = node.tag[1:]

    prefix = "" if tag in ["Ref", "Condition"] else "Fn::"
    cfntag = prefix + tag

    if tag == "GetAtt" and isinstance(node.value, string_types):
        # ShortHand notation for !GetAtt accepts Resource.Attribute format
        # while the standard notation is to use an array
        # [Resource, Attribute]. Convert shorthand to standard format
        value = node.value.split(".", 1)

    elif isinstance(node, ScalarNode):
        # Value of this node is scalar
        value = loader.construct_scalar(node)

    elif isinstance(node, SequenceNode):
        # Value of this node is an array (Ex: [1,2])
        value = loader.construct_sequence(node)

    else:
        # Value of this node is an mapping (ex: {foo: bar})
        value = loader.construct_mapping(node)

    return {cfntag: value}

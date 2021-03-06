# Copyright 2018 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from kfp.dsl import Pipeline, PipelineParam, ContainerOp, ExitHandler, OpsGroup
import unittest


class TestOpsGroup(unittest.TestCase):
  
  def test_basic(self):
    """Test basic usage."""
    with Pipeline('somename') as p:
      self.assertEqual(1, len(p.groups))
      with OpsGroup(group_type='exit_handler'):
        op1 = ContainerOp(name='op1', image='image')
        with OpsGroup(group_type='branch'):
          op2 = ContainerOp(name='op2', image='image')
          op3 = ContainerOp(name='op3', image='image')
        with OpsGroup(group_type='loop'):
          op4 = ContainerOp(name='op4', image='image')

    self.assertEqual(1, len(p.groups))
    self.assertEqual(1, len(p.groups[0].groups))
    exit_handler_group = p.groups[0].groups[0]
    self.assertEqual('exit_handler', exit_handler_group.type)
    self.assertEqual(2, len(exit_handler_group.groups))
    self.assertEqual(1, len(exit_handler_group.ops))
    self.assertEqual('op1', exit_handler_group.ops[0].name)

    branch_group = exit_handler_group.groups[0]
    self.assertFalse(branch_group.groups)
    self.assertCountEqual([x.name for x in branch_group.ops], ['op2', 'op3'])

    loop_group = exit_handler_group.groups[1]
    self.assertFalse(loop_group.groups)
    self.assertCountEqual([x.name for x in loop_group.ops], ['op4'])


class TestExitHandler(unittest.TestCase):
  
  def test_basic(self):
    """Test basic usage."""
    with Pipeline('somename') as p:
      exit_op = ContainerOp(name='exit', image='image')
      with ExitHandler(exit_op=exit_op):
        op1 = ContainerOp(name='op1', image='image')

    exit_handler = p.groups[0].groups[0]
    self.assertEqual('exit_handler', exit_handler.type)
    self.assertEqual('exit', exit_handler.exit_op.name)
    self.assertEqual(1, len(exit_handler.ops))
    self.assertEqual('op1', exit_handler.ops[0].name)

  def test_invalid_exit_op(self):
    with self.assertRaises(ValueError):
      with Pipeline('somename') as p:
        op1 = ContainerOp(name='op1', image='image')
        exit_op = ContainerOp(name='exit', image='image')
        exit_op.after(op1)
        with ExitHandler(exit_op=exit_op):
          pass

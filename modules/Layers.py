
# Define custom layers here and add them to the global_layers_list dict (important!)
global_layers_list = {}

import DeepJetCore
import keras
from keras.layers import Layer
import keras.backend as K
import tensorflow as tf
from caloGraphNN import *
from caloGraphNN_keras import GlobalExchange
global_layers_list['GlobalExchange']=GlobalExchange  




class TestLayer(Layer):
    def __init__(self, **kwargs):
        super(TestLayer, self).__init__(**kwargs)
        
        self.dense1 = keras.layers.Dense(10)
        self.dense2 = keras.layers.Dense(10)
    
    def build(self, input_shape):
        self.dense1.build(input_shape)
        self.dense2.build(input_shape)
        
        super(TestLayer, self).build(input_shape)
    
    def call(self, inputs):
        x1 = self.dense1(inputs)
        x2 = self.dense2(inputs)
        return tf.concat([x1,x2],axis=-1)
        
    def compute_output_shape(self, input_shape):
        return (input_shape[0],input_shape[1],20)
        
    def get_config(self):
        base_config = super(TestLayer, self).get_config()
        return dict(list(base_config.items()))


       
global_layers_list['TestLayer']=TestLayer 


class MergeActiveHits(Layer):
    '''
    Input: B x V x F, B x V x 1 hitmatched mask
    Output: B x F
    '''
    def __init__(self, **kwargs):
        super(MergeActiveHits, self).__init__(**kwargs)
    
    def compute_output_shape(self, input_shape):
        inp = input_shape[0]
        #masks = input_shape[1]
        
        return (inp[0],inp[2])
    
    def call(self, inputs):
        
        indiv_correction = inputs[0]
        mask = inputs[1]
        
        correction_factors = tf.reduce_sum(indiv_correction*mask,axis=1)
        correction_factors /= tf.cast(tf.count_nonzero(mask, axis=1), dtype='float32')+K.epsilon() #B x F
        return correction_factors
    
    #just inherit def get_config(self):
    def get_config(self):
        base_config = super(MergeActiveHits, self).get_config()
        return dict(list(base_config.items()))
        
       
global_layers_list['MergeActiveHits']=MergeActiveHits   

class ReduceMeanVertices(Layer): 
    def __init__(self, **kwargs):
        super(ReduceMeanVertices, self).__init__(**kwargs)
    
    def compute_output_shape(self, input_shape):
        return (input_shape[0],input_shape[2])
    
    def call(self, inputs):
        return tf.reduce_mean(inputs,axis=1)
    
    def get_config(self):
        base_config = super(ReduceMeanVertices, self).get_config()
        return dict(list(base_config.items()))
    

global_layers_list['ReduceMeanVertices']=ReduceMeanVertices   





class GravNet_simple(tf.keras.layers.Layer):
    def __init__(self, 
                 n_neighbours, 
                 n_dimensions, 
                 n_filters, 
                 n_propagate,**kwargs):
        super(GravNet_simple, self).__init__(**kwargs)
        
        self.n_neighbours = n_neighbours
        self.n_dimensions = n_dimensions
        self.n_filters = n_filters
        self.n_propagate = n_propagate
        
        self.input_feature_transform = tf.keras.layers.Dense(n_propagate)
        self.input_spatial_transform = tf.keras.layers.Dense(n_dimensions)
        self.output_feature_transform = tf.keras.layers.Dense(n_filters, activation='tanh')

    def build(self, input_shape):
        
        self.input_feature_transform.build(input_shape)
        self.input_spatial_transform.build(input_shape)
        
        self.output_feature_transform.build((input_shape[0], input_shape[1], 
                                             input_shape[2] + self.input_feature_transform.units * 2))
 
        super(GravNet_simple, self).build(input_shape)
        
    def call(self, x):
        
        coordinates = self.input_spatial_transform(x)
        features = self.input_feature_transform(x)
        collected_neighbours = self.collect_neighbours(coordinates, features)
        
        updated_features = tf.concat([x, collected_neighbours], axis=-1)
        return self.output_feature_transform(updated_features)
    

    def compute_output_shape(self, input_shape):
        return (input_shape[0], input_shape[1], self.output_feature_transform.units)
    
    def collect_neighbours(self, coordinates, features):
        
        distance_matrix = euclidean_squared(coordinates, coordinates)
        ranked_distances, ranked_indices = tf.nn.top_k(-distance_matrix, self.n_neighbours)

        neighbour_indices = ranked_indices[:, :, 1:]
        
        n_batches = tf.shape(features)[0]
        n_vertices = tf.shape(features)[1]
        n_features = tf.shape(features)[2]
        
        batch_range = tf.range(0, n_batches)
        batch_range = tf.expand_dims(batch_range, axis=1)
        batch_range = tf.expand_dims(batch_range, axis=1)
        batch_range = tf.expand_dims(batch_range, axis=1) # (B, 1, 1, 1)

        # tf.ragged FIXME? n_vertices
        batch_indices = tf.tile(batch_range, [1, n_vertices, self.n_neighbours - 1, 1]) # (B, V, N-1, 1)
        vertex_indices = tf.expand_dims(neighbour_indices, axis=3) # (B, V, N-1, 1)
        indices = tf.concat([batch_indices, vertex_indices], axis=-1)
    
    
        distance = -ranked_distances[:, :, 1:]
    
        weights = gauss_of_lin(distance * 10.)
        weights = tf.expand_dims(weights, axis=-1)
        
        neighbour_features = tf.gather_nd(features, indices)
        neighbour_features *= weights
        neighbours_max = tf.reduce_max(neighbour_features, axis=2)
        neighbours_mean = tf.reduce_mean(neighbour_features, axis=2)
        
        return tf.concat([neighbours_max, neighbours_mean], axis=-1)
    
    def get_config(self):
        config = {'n_neighbours': self.n_neighbours, 
                  'n_dimensions': self.n_dimensions, 
                  'n_filters': self.n_filters, 
                  'n_propagate': self.n_propagate}
        base_config = super(GravNet_simple, self).get_config()
        return dict(list(base_config.items()) + list(config.items()))



global_layers_list['GravNet_simple']=GravNet_simple   



 